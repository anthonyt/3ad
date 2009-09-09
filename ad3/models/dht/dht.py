import ad3.models.abstract
import simplejson
import hashlib
import urllib
import tempfile
import random
import os
import copy
import entangled
import entangled.dtuple
import entangled.kademlia.contact
import entangled.kademlia.msgtypes
from entangled.kademlia.node import rpcmethod
from entangled.kademlia.protocol import KademliaProtocol
from time import time
from sets import Set
from twisted.internet import defer
from twisted.internet import reactor
from functools import partial

import logging
logger = logging.getLogger('3ad')

offload_result_timeout = 300 # 5 minutes; client must download and process vector in this time
offload_poll_wait = 10 # 10 seconds between node.pollOffloadedCalculation calls

class KeyAggregator(object):
    # Once initialized with a list of tuples to match against
    def __init__(self, net_handler, tuple_list):
        self.net_handler = net_handler
        self.tuple_list = tuple_list
        self.key_lists = []

    def got_tuples(self, tuples, dTuple):
        # Got a new list of tuples...
        if tuples is None:
            tuples = []
            logger.debug("KeyAggregator found no keys on network for %r", dTuple)
        else:
            logger.debug("KeyAggregator found keys on network for %r", dTuple)

        keys = [t[1] for t in tuples]
        logger.debug("KeyAggregator Got Key List: %r", keys)

        self.key_lists.append(keys)

    def done(self, val):
        # Get the maximum intersecting set of keys in all tuples.
        keys = Set(self.key_lists[0])

        for ks in self.key_lists[1:]:
            keys = keys.intersection(ks)

        return list(keys)

    def go(self):
        # for each search tuple, run our got_tuples function on the resulting tuple rows
        dfs = []
        for dTuple in self.tuple_list:
            df = self.net_handler.dht_get_tuples(dTuple)
            df.addCallback(self.got_tuples, dTuple)

        list_df = defer.DeferredList(dfs)
        list_df.addCallback(self.done)

        return list_df


class ObjectAggregator(object):
    # Once initialized with a list of hash keys
    # the ObjectAggregator can be instructed to create a
    # list of objects represented by the data at those keys
    # and asynchronously pass that list to a callback function

    def __init__(self, net_handler, key_list):
        self.net_handler = net_handler
        self.key_list = key_list
        self.objects = []

    def go(self):
        outer_df = defer.Deferred()

        def got_value(value):
            # append this value to our list
            obj = self.net_handler.obj_from_row(value)
            got_obj(obj)

        def got_obj(obj):
            self.objects.append(obj)

            # if we have got all the values we asked for
            # call the callback function
            if len(self.objects) == len(self.key_list):
                outer_df.callback(self.objects)

        # for each key, run our got_value function on the value row
        for key in self.key_list:
#            logger.debug("-> Searching for key.. %r", key.encode('hex'))
            o = self.net_handler.cache_get_obj(key)
            if o is not None:
                got_obj(o)
            else:
                df = self.net_handler.dht_get_value(key)
                df.addCallback(got_value)

        return outer_df


class NetworkHandler(object):
    def __init__(self, node):
        self.node = node
        self._cache = {}

    def obj_from_row(self, row):
        logger.debug("-> OBJ FROM ROW %r", row)
        h = simplejson.loads(row)

        if h['type'] == "plugin":
            o = Plugin(h['name'], h['module_name'], h['key'].decode('hex'))

        elif h['type'] == "plugin_output":
            o = PluginOutput(h['vector'], h['plugin_key'], h['audio_key'], h['key'].decode('hex'))

        elif h['type'] == "tag":
            o = Tag(h['name'], h['vector'], h['key'].decode('hex'))

        elif h['type'] == "audio_file":
            o = AudioFile(h['file_name'], h['vector'], h['user_name'], h['key'].decode('hex'))

        else:
            o = None

        if o is not None:
            self.cache_store_obj(h['key'].decode('hex'), o)

        return o


    def hash_function(self, plain_key):
        logger.debug("-> Generating a hash for %r", plain_key)
        h = hashlib.sha1()
        h.update(plain_key)
        return h.digest()


    def dht_get_value(self, key):
        def success(result):
            # return a useful value
            if type(result) == dict:
                return result[key]
            else:
                return None

        def error(failure):
            logger.debug("-> An error occurred: %s", failure.getErrorMessage())
            return None

        df = self.node.iterativeFindValue(key)
        # use the "success" function to filter our result before
        # passing it to the callback
        df.addCallback(success)
#        df.addErrback(error)
        return df


    def dht_store_value(self, key, value):
        def success(result):
            logger.debug("dht_store_value: %s => %r on %r", key.encode('hex'), value, result)
            return result

        logger.debug("-> Attempting to store value %s => %r", key.encode('hex'), value)
        df = self.node.iterativeStore(key, value)
        df.addCallback(success)
        return df


    def dht_get_tuples(self, dTuple):
        def success(result):
            """
            @type result  tuple or None
            """
            logger.debug("dht_get_tuples: %r %r", result, dTuple)
            return result

        def error(failure):
            logger.debug("dht_get_tuples: %r, %s", dTuple, failure.getErrorMessage())
            return None

        logger.debug("-> searching for tuples based on %r", dTuple)
        df = self.node.readIfExists(dTuple, 0)
        df.addCallback(success)
        df.addErrback(error)
        return df

    def dht_remove_tuples(self, dTuple):
        logger.debug("Removing tuples matching %r", dTuple)
        df = defer.Deferred()
        outer_df = defer.Deferred()

        def done(result):
            outer_df.callback(result)

        def get_next_tuple(result):
            if result is not None:
                df.addCallback(get_next_tuple)
                df_g = self.node.getIfExists(dTuple)
                return df_g
            else:
                df.addCallback(done)
                return None

        df.addCallback(get_next_tuple)
        df.callback('go')

        return outer_df

    def dht_store_tuple(self, dTuple):
        def success(result):
            logger.debug("-> dht_store_tuple: %r", dTuple)
            return result

        def error(failure):
            logger.debug("-> dht_store_tuple: %r %s",
                    dTuple, failure.getErrorMessage())
            pass

        logger.debug("-> Attempting to store tuple: %r", dTuple)
        df = self.node.put(dTuple, trackUsage=False)
        df.addCallback(success)
        df.addErrback(error)
        return df


    def get_objects_matching_tuples(self, tuple_list):
        """
        Return a list of the appropriate objects for each object row
        that matches all of the provided search tuples in the tuple_list

        NB: providing an empty tuple list will result in no callback being fired
        """
        outer_df = defer.Deferred()

        def got_keys(keys):
            if len(keys) == 0:
                logger.debug("-> KA object found nothing.")
                outer_df.callback([])
            else:
                # if we actually have keys returned
                # call our tuple agregator to find corresponding value rows
                logger.debug("-> KA object found %d keys. Making a OA object with key list.", len(keys))
                ta = ObjectAggregator(self, keys)
                ta_df = ta.go()
                ta_df.addCallback(outer_df.callback)

        logger.debug("-> Making a KA object with tuple list: %r", tuple_list)
        ka = KeyAggregator(self, tuple_list)
        ka_df = ka.go()
        ka_df.addCallback(got_keys)

        return outer_df


    def get_object_matching_tuples(self, tuple_list):
        """
        Return a single object representing the first object row
        that matches all of the provided search tuples in the tuple_list

        NB: providing an empty tuple list will result in no callback being fired
        """
        def pick_one(obj_list):
            if len(obj_list) > 0:
                return obj_list[0]
            else:
                return None

        df = self.get_objects_matching_tuples(tuple_list)
        df.addCallback(pick_one)
        return df


    def cache_get_obj(self, key):
        """
        if the object exists in our cache
        and its lifetime has not expired
        return it. else return None
        """
        if key in self._cache:
            entry = self._cache[key]
            if int(time()) < entry[0]:
                logger.debug("-> Fetching object from the cache %r TTL: %d s", entry[1], int(time()) - entry[0])
                return entry[1]

        return None

    def cache_store_obj(self, key, obj):
        """
        store the object in our cache
        with an end of life timestamp
        """
        lifetime = int(time()) + 300
        self._cache[key] = (lifetime, obj)


_network_handler = None
plugins = []

def set_network_handler(obj):
    """
    set the network handler object.
    should be an instance of the network handler class above
    will be used by all functions below

    Also defines the plugins that will be used by 3ad.
    """
    logger.debug("-> setting network handler! %r", obj)
    global _network_handler, plugins
    _network_handler = obj

    # Define our plugins:
    plugins = [
#        Plugin('charlotte', 'ad3.analysis_plugins.charlotte'),
        Plugin('bextract', 'ad3.analysis_plugins.bextract_plugin'),
#        Plugin('centroid', 'ad3.analysis_plugins.centroid_plugin')
    ]

def get_network_handler():
    return _network_handler

class SaveableModel(object):
    def get_key(self):
        return self.key or self._get_key()

    def _get_key():
        return None

    def _get_tuple():
        return ()

    def _save(self, my_hash):
        """ Save this object to the DHT.

        Immediately returns a deferred which will return
        this object, after it has been saved.
        """
        outer_df = defer.Deferred()
        df = defer.Deferred()

        def save_my_tuple(val):
            logger.debug("save_my_tuple() called for %r", self)
            my_tuple = self._get_tuple()
            df = _network_handler.dht_store_tuple(my_tuple)
            return df

        def save_value(val):
            my_hash['key'] = self.key.encode('hex')
            my_string = simplejson.dumps(my_hash)
            df = _network_handler.dht_store_value(self.key, my_string)
            return df

        def done(val):
            outer_df.callback(self)

        if self.key is None:
            self.key = self._get_key()
            df.addCallback(save_my_tuple)

        df.addCallback(save_value)
        df.addCallback(done)
        df.callback(None)

        return outer_df

class Plugin(ad3.models.abstract.Plugin, SaveableModel):
    """
    Plugin Object

    Attributes:
        name
        module_name
        key

    Methods:
        create_vector(audiofile)
        save()
    """

    def __init__(self, name, module_name, key = None):
        ad3.models.abstract.Plugin.__init__(self, name, module_name)
        if key:
            self.key = key
        else:
            self.key = self._get_key()

    def _get_key(self):
        r = _network_handler.hash_function("plugin_" + self.name + self.module_name)
        return r

    def _get_tuple(self):
        my_tuple = ("plugin", self.key, self.name, self.module_name)
        return my_tuple

#    def save(self):
#        my_hash = {
#            'name': self.name,
#            'module_name': self.module_name,
#            'type': 'plugin'
#        }
#        df = self._save(my_hash)
#        return df

class AudioFile(ad3.models.abstract.AudioFile, SaveableModel):
    """
    Audio File Object

    Attributes:
        name
        vector
        key

    Method:
        getKey
    """

    def __init__(self, file_name, vector = None, user_name = "", key = None):
        ad3.models.abstract.AudioFile.__init__(self, file_name)

        self.vector = vector
        self.key = key
        self.user_name = user_name

    def __repr__(self):
        return "<AudioFile('%s', '%s')>" % (self.file_name, self.user_name)

    def _get_key(self):
        r = _network_handler.hash_function("audio_file_" + self.file_name + self.user_name)
        return r

    def _get_tuple(self):
        my_tuple = ("audio_file", self.key, self.file_name, self.user_name)
        return my_tuple

    def save(self):
        my_hash = {
            'file_name': self.file_name,
            'vector': self.vector,
            'user_name': self.user_name,
            'type': 'audio_file'
        }
        df = self._save(my_hash)
        return df

class Tag(ad3.models.abstract.Tag, SaveableModel):
    """
    Tag Object

    Attributes:
        name
        vector
        key
    """

    def __init__(self, name, vector = None, key = None):
        self.name = name
        self.vector = vector
        self.key = key

    def _get_key(self):
        return _network_handler.hash_function("tag_" + self.name)

    def _get_tuple(self):
        my_tuple = ("tag", self.key, self.name)
        return my_tuple

    def save(self):
        my_hash = {
            'name': self.name,
            'vector': self.vector,
            'type': 'tag'
        }
        df = self._save(my_hash)
        return df


class PluginOutput(ad3.models.abstract.PluginOutput, SaveableModel):
    """
    Object to represent the output of a plugin

    Attributes:
        vector
        plugin_key
        file_key
        key
    """

    def __init__(self, vector, plugin_key = None, audio_key = None,  key = None):
        self.vector = vector
        self.plugin_key = plugin_key
        self.audio_key = audio_key
        self.key = key

    def _get_key(self):
        return _network_handler.hash_function("plugin_output_"+str(self.vector))

    def save(self):
        # We've got a bunch of stuff to do. Don't call __save(), just do it.
        outer_df = defer.Deferred()
        df = defer.Deferred()

        def done(val):
            outer_df.callback(self)

        def save_audio_tuple(val):
            # make an audio_file row for cross referencing
            audio_tuple = ("audio_file", self.audio_key, "plugin_output", self.key)
            df = _network_handler.dht_store_tuple(audio_tuple)
            return df

        def save_plugin_tuple(val):
            # make a plugin row for cross referencing
            plugin_tuple = ("plugin", self.plugin_key, "plugin_output", self.key)
            df = _network_handler.dht_store_tuple(plugin_tuple)
            return df

        def save_my_tuple(val):
            # store a plugin_output row
            my_tuple = ("plugin_output", self.key, self.plugin_key, self.audio_key)
            df =_network_handler.dht_store_tuple(my_tuple)
            return df

        def save_value(val):
            # store the object state
            my_hash = {'vector': self.vector,
                       'key': self.key.encode('hex'),
                       'plugin_key': self.plugin_key.encode('hex'),
                       'audio_key': self.audio_key.encode('hex'),
                       'type': 'plugin_output'}
            my_string = simplejson.dumps(my_hash)
            df = _network_handler.dht_store_value(self.key, my_string)
            return df


        if self.key is None:
            self.key = self._get_key()
            # chain our tuple saving procedures, so they don't happen at the same time
            df.addCallback(save_my_tuple)
            df.addCallback(save_plugin_tuple)
            df.addCallback(save_audio_tuple)

        df.addCallback(save_value)
        df.addCallback(done)
        df.callback(None)

        return outer_df



def get_tags(name = None, audio_file = None, guessed_file = None):
    """ Return a deferred, which will be called back with a list of Tag objects.
    By default returns all tags.

    @param name: return only tags with tag.name matching provided name
    @type  name: unicode

    @param audio_file: return only tags that have been applied to this audio file
    @type  audio_file: AudioFile object

    @param guessed_file: return only tags that have been guessed for this audio file
    @type  guessed_file: AudioFile object
    """
    search_tuples = [ ("tag", None, name) ]
    if audio_file is not None:
        search_tuples.append( ("tag", None, "audio_file", audio_file.get_key()) )
    if guessed_file is not None:
        search_tuples.append( ("tag", None, "guessed_file", guessed_file.get_key()) )

    df = _network_handler.get_objects_matching_tuples(search_tuples)
    return df

def get_tag(name):
    """ Returns a deferred, which will be called back with a single Tag object.
    If no such Tag exists in the data store, passes None to the callback.

    @param name: the name of the tag object to return
    @type  name: unicode
    """
    search_tuples = [("tag", None, name)]
    df = _network_handler.get_object_matching_tuples(search_tuples)
    return df

def get_plugin_outputs(audio_file=None, plugin=None):
    if audio_file is not None:
        audio_key = audio_file.get_key()
    else:
        audio_key = None
    if plugin is not None:
        plugin_key = plugin.get_key()
    else:
        plugin_key = None

    search_tuples = [ ("plugin_output", None, plugin_key, audio_key) ]
    df = _network_handler.get_objects_matching_tuples(search_tuples)
    return df

def get_plugin_output(audio_file, plugin):
    search_tuples = [ ("plugin_output", None, plugin.get_key(), audio_file.get_key()) ]
    df = _network_handler.get_objects_matching_tuples(search_tuples)
    return df

def get_plugins(name = None, module_name = None, plugin_output = None):
    """ Returns a deferred, which will be called back with a list of Plugin objects.
    By default returns all plugins.

    @param name: if provided, returns only plugins with a matching name
    @type  name: unicode

    @param module_name: if provided, returns only plugins with a matching module_name
    @type  module_name: unicode

    @param plugin_output: if provided, returns only the plugin associated with this object
    @type  plugin_output: PluginOutput object
    """
    # Note that we hardcode the Plugins now in 3ad, so this will look in our
    # predefined list.
    ps = copy.copy(plugins)

    if module_name:
        ps = [p for p in ps if p.module_name == module_name]

    if plugin_output:
        ps = [p for p in ps if p.key == plugin_output.plugin_key]

    df = defer.Deferred()
    df.callback(ps)
    return df

def get_plugin(name = None, module_name = None, plugin_output = None):
    """ Return a deferred, which will be called back with a single Plugin object.

    @param name: if provided, returns only plugins with a matching name
    @type  name: unicode

    @param module_name: if provided, returns only plugins with a matching module_name
    @type  module_name: unicode

    @param plugin_output: if provided, returns only the plugin associated with this object
    @type  plugin_output: PluginOutput object
    """
    search_tuples = [ ("plugin", None, name, module_name) ]
    if plugin_output is not None:
        search_tuples.append( ("plugin", None, "plugin_output", plugin_output.get_key()) )
    df = _network_handler.get_object_matching_tuples(search_tuples)

def get_audio_files(file_name=None, user_name=None, tag=None, guessed_tag=None, plugin_output=None):
    """ Return a deferred, which will be called back with a list of AudioFile objects.
    By default returns all audio files.

    @param file_name: if provided, returns only files with a matching file name
    @type  file_name: unicode

    @param user_name: if provided, returns only files with a matching user name
    @type  user_name: unicode

    @param tag: if provided, returns only files manually tagged with the provided tag
    @type  tag: Tag object

    @param guessed_tag: if provided, returns only files automatically tagged with the provided tag
    @type  guessed_tag: Tag object

    @param plugin_output: if provided, returns only the file associated with this output
    @type  plugin_output: PluginOutput object
    """
    search_tuples = [ ("audio_file", None, file_name, user_name) ]
    if tag is not None:
        search_tuples.append( ("audio_file", None, "tag", tag.get_key()) )
    if guessed_tag is not None:
        search_tuples.append( ("audio_file", None, "guessed_tag", guessed_tag.get_key()) )
    if plugin_output is not None:
        search_tuples.append( ("audio_file", None, "plugin_output", plugin_output.get_key()) )

    df = _network_handler.get_objects_matching_tuples(search_tuples)
    return df

def get_audio_file(file_name=None, user_name=None, tag=None, guessed_tag=None, plugin_output=None):
    """ Returns a deferred, which will be called back with a list of AudioFile objects.
    By default returns all audio files.

    @param file_name: if provided, returns only files with a matching file name
    @type  file_name: unicode

    @param user_name: if provided, returns only files with a matching user name
    @type  user_name: unicode

    @param tag: if provided, returns only files manually tagged with the provided tag
    @type  tag: Tag object

    @param guessed_tag: if provided, returns only files automatically tagged with the provided tag
    @type  guessed_tag: Tag object

    @param plugin_output: if provided, returns only the file associated with this output
    @type  plugin_output: PluginOutput object
    """
    search_tuples = [ ("audio_file", None, file_name, user_name) ]
    if tag is not None:
        search_tuples.append( ("audio_file", None, "tag", tag.get_key()) )
    if guessed_tag is not None:
        search_tuples.append( ("audio_file", None, "guessed_tag", guessed_tag.get_key()) )
    if plugin_output is not None:
        search_tuples.append( ("audio_file", None, "plugin_output", plugin_output.get_key()) )

    df = _network_handler.get_object_matching_tuples(search_tuples)
    return df


def save(obj):
    """ Save an object to permanent storage.

    @param obj: the object to save
    @type  obj: Saveable
    """
    logger.debug("-> saving object... %r", obj)
    df = obj.save()
    return df

def special_generate_plugin_vectors(audio_file):
    """ Attempts to farm out vector calculation over the network.

    Immediately returns a deferred that will either return a vector dict
    or None, depending on the success or failure of the offloading operation.

    @param audio_file: the audio file to run the plugins on
    @type  audio_file: AudioFile
    """
    logger.debug("------\n -> Beginning update vector")

    # Mutable object to store the contact we offloaded to, and status info.
    # sendOffloadCommand() method updates the value of this dict.
    struct = {
        'contact': None,
        'file_uri': urllib.quote(audio_file.file_name),
        'file_name': audio_file.file_name,
        'file_key': audio_file.get_key(),
        'timestamp': int(time())
    }

    outer_df = defer.Deferred()

    def fail():
        outer_df.callback(None)

    def succeed(vectors):
        outer_df.callback(vectors)

    def got_poll_response(response):
        # response dict will be a copy of the entry in the contact's
        # node.computations dict. As such, it will have the following fields:
        # 'complete', 'vectors', 'failed', 'downloaded'
        #  bool        dict       bool      bool

        if not isinstance(response, dict):
            # Oh noes, error condition!
            logger.debug("Poll: probably timed out %r", response)
            fail()
            return None

        if response['failed']:
            logger.debug("Poll: failed")
            fail()
        elif response['complete']:
            logger.debug("Poll: complete!")
            succeed(response['vectors'])
        else:
            # schedule another poll
            logger.debug("Poll: unfinished. Sheduling another poll.")
            schedule_poll()

        return None

    def send_poll():
        if int(time()) - struct['timestamp'] > offload_result_timeout:
            # timed out. just calculate it yourself
            logger.debug("Offloaded transaction timed out. Computing locally.")
            fail()
        else:
            logger.debug("Polling...")
            # execute a poll and call the "got_poll_response" method when it's done
            df = _network_handler.node.pollOffloadedCalculation(struct)
            df.addBoth(got_poll_response)

    def got_response(response):
        if response == "OK":
            # Found a node that accepted our offload request!
            # start the polling loop here.
            logger.debug("Offload request accepted.")
            schedule_poll()
        else:
            # Couldn't find a node to accept our offload request.
            # Calculate it locally.
            logger.debug("Offload request rejected.")
            fail()

    schedule_poll = partial(reactor.callLater, offload_poll_wait, send_poll)

    logger.debug("Attempting to farm out vector calculation")
    df = _network_handler.node.sendOffloadCommand(struct)
    df.addCallback(got_response)

    return outer_df

def initialize_storage(callback):
    """ Initializes an empty storage environment.

    For a database, this might mean to (re)create all tables.
    """
    pass

def apply_tag_to_file(audio_file, tag):
    logger.info("APPLYING TAG TO FILE: %r %r", tag, audio_file)

    tag_tuple = ("tag", tag.get_key(), "audio_file", audio_file.get_key())
    audio_tuple = ("audio_file", audio_file.get_key(), "tag", tag.get_key())

    def save_tag_tuple(val):
        tag_df = _network_handler.dht_store_tuple(tag_tuple)
        return tag_df

    def save_audio_tuple(val):
        audio_df = _network_handler.dht_store_tuple(audio_tuple)
        return audio_df

    # chain our tuple saving procedures, so they don't happen at the same time
    df = defer.Deferred()
    df.addCallback(save_tag_tuple)
    df.addCallback(save_audio_tuple)
    df.callback(None)
    return df

def remove_guessed_tags():
    outer_df = defer.Deferred()
    logger.debug("_")

    def done(val):
        logger.debug("remove_guessed_tags")
        outer_df.callback(val)

    def remove_tag_tuples(val):
        logger.debug("remove_guessed_tags")
        tag_tuple = ("tag", None, "guessed_file", None)
        df = _network_handler.dht_remove_tuples(tag_tuple)
        return df

    def remove_audio_tuples(val):
        logger.debug("remove_guessed_tags")
        audio_tuple = ("audio_file", None, "guessed_tag", None)
        df = _network_handler.dht_remove_tuples(audio_tuple)
        return df

    df = defer.Deferred()
    df.addCallback(remove_tag_tuples)
    df.addCallback(remove_audio_tuples)
    df.addCallback(done)
    df.callback(None)

    return outer_df



def guess_tag_for_file(audio_file, tag):
    outer_df = defer.Deferred()

    tag_tuple = ("tag", tag.get_key(), "guessed_file", audio_file.get_key())
    audio_tuple = ("audio_file", audio_file.get_key(), "guessed_tag", tag.get_key())

    def save_tag_tuple(val):
       df = _network_handler.dht_store_tuple(tag_tuple)
       return df

    def save_audio_tuple(val):
        df = _network_handler.dht_store_tuple(audio_tuple)
        return df

    def done(val):
        outer_df.callback(val)

    # chain our tuple saving procedures, so they don't happen at the same time
    df = defer.Deferred()
    df.addCallback(save_audio_tuple)
    df.addCallback(save_tag_tuple)
    df.addCallback(done)
    df.callback(None)

    return outer_df


# this only runs if the module was *not* imported
if __name__ == '__main__':
        main()


