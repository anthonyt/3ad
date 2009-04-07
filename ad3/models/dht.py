import ad3.models.abstract
import simplejson
import hashlib
import urllib
import tempfile
import random
import os
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

class KeyAggregator(object):
    # Once initialized with a list of tuples to match against
    def __init__(self, net_handler, tuple_list):
        self.net_handler = net_handler
        self.tuple_list = tuple_list
        self.key_lists = []

    def go(self, callback):
        def got_tuples(tuples):
            keys = [t[1] for t in tuples]

            self.key_lists.append(keys)

            # if we have got all the values we asked for,
            # find the common keys, and call the callback function
            if len(self.key_lists) == len(self.tuple_list):
                keys = Set(self.key_lists[0])

                for ks in self.key_lists[1:]:
                    keys = keys.intersection(ks)

                callback(list(keys))

        def cache_tuples(dTuple, result_tuples):
            if result_tuples is None:
                result_tuples = []
            # add these tuples to the cache!!
            self.net_handler.cache_store_tuples(dTuple, result_tuples)
            # continue execution
            got_tuples(result_tuples)

        # for each search tuple, run our got_tuples function on the resulting tuple rows
        for dTuple in self.tuple_list:
            # attempt to fetch cached results
            result_tuples = self.net_handler.cache_get_tuples(dTuple)
            if result_tuples is not None:
                got_tuples(result_tuples)
            else:
                # if there are no cached results, get new results
                self.net_handler.dht_get_tuples(dTuple, partial(cache_tuples, dTuple))


class ObjectAggregator(object):
    # Once initialized with a list of hash keys
    # the ObjectAggregator can be instructed to create a
    # list of objects represented by the data at those keys
    # and asynchronously pass that list to a callback function

    def __init__(self, net_handler, key_list):
        self.net_handler = net_handler
        self.key_list = key_list
        self.objects = []

    def go(self, callback):
        def got_value(value):
            # append this value to our list
            obj = self.net_handler.obj_from_row(value)
            self.objects.append(obj)

            # if we have got all the values we asked for
            # call the callback function
            if len(self.objects) == len(self.key_list):
                callback(self.objects)

        # for each key, run our got_value function on the value row
        for key in self.key_list:
#            #print "->", "Searching for key..", key.encode('hex')
            o = self.net_handler.cache_get_obj(key)
            if o is not None:
                self.objects.append(o)
                if len(self.objects) == len(self.key_list):
                    # FIXME: this could well be a race condition with the similar statement above
                    callback(self.objects)
            else:
                self.net_handler.dht_get_value(key, got_value)



class NetworkHandler(object):
    def __init__(self, node):
        self.node = node
        self._cache = {}

    def obj_from_row(self, row):
        #print "->", "OBJ FROM ROW", row
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
        #print "->", "Generating a hash for", plain_key
        h = hashlib.sha1()
        h.update(plain_key)
        return h.digest()


    def dht_get_value(self, key, callback):
        def success(result):
            # return a useful value
            if type(result) == dict:
                return result[key]
            else:
                return None

        def error(failure):
            print "->", 'An error occurred:', failure.getErrorMessage()
            callback(None)

        df = self.node.iterativeFindValue(key)
        # use the "success" function to filter our result before
        # passing it to the callback
        df.addCallback(success)
        df.addCallback(callback)
#        df.addErrback(error)
        return df


    def dht_store_value(self, key, value):
        def success(result):
            #print "->", 'stored value:', result
            return result

        #print "->", "Attempting to store value", key.encode('hex'), "=>", value
        df = self.node.iterativeStore(key, value)
        df.addCallback(success)
        return df


    def dht_get_tuples(self, dTuple, callback):
        def success(result):
            """
            @type result  tuple or None
            """
            callback(result)

        def error(failure):
            print "->", 'an error occurred:', failure.getErrorMessage()
            callback(None)

#        #print "->", "searching for tuples based on", dTuple
        df = self.node.readIfExists(dTuple, 0)
        df.addCallback(success)
#        df.addErrback(error)
        return df

    def dht_remove_tuples(self, dTuple):
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
            #print "->", 'stored tuple:', result
            return result

        def error(failure):
            print "->", 'an error occurred:', failure.getErrorMessage()

        #print "->", "Attempting to store tuple:", dTuple
        df = self.node.put(dTuple, trackUsage=False)
        df.addCallback(success)
#        df.addErrback(error)
        return df


    def get_objects_matching_tuples(self, tuple_list, callback):
        """
        Return a list of the appropriate objects for each object row
        that matches all of the provided search tuples in the tuple_list

        NB: providing an empty tuple list will result in no callback being fired
        """
        def got_keys(keys):
            if len(keys) == 0:
                #print "->", "KA object found nothing."
                callback([])
            else:
                # if we actually have keys returned
                # call our tuple agregator to find corresponding value rows
                #print "->", "KA object found", len(keys), "keys. Making a OA object with key list."
                ta = ObjectAggregator(self, keys)
                ta.go(callback)

        #print "->", "Making a KA object with tuple list:", tuple_list
        ka = KeyAggregator(self, tuple_list)
        ka.go(got_keys)

    def get_object_matching_tuples(self, tuple_list, callback):
        """
        Return a single object representing the first object row
        that matches all of the provided search tuples in the tuple_list

        NB: providing an empty tuple list will result in no callback being fired
        """
        def pick_one(obj_list):
            if len(obj_list) > 0:
                callback(obj_list[0])
            else:
                callback(None)

        self.get_objects_matching_tuples(tuple_list, pick_one)


    def cache_get_obj(self, key):
        """
        if the object exists in our cache
        and its lifetime has not expired
        return it. else return None
        """
        if key in self._cache:
            entry = self._cache[key]
            if int(time()) < entry[0]:
                print "-> Fetching object from the cache", entry[1], "TTL:", int(time()) - entry[0], 's'
                return entry[1]

        return None

    def cache_store_obj(self, key, obj):
        """
        store the object in our cache
        with an end of life timestamp
        """
        lifetime = int(time()) + 300
        self._cache[key] = (lifetime, obj)

    def cache_get_tuples(self, search_tuple):
        """
        if the tuple list exists in our cache
        and its lifetime has not expired
        return it. else return None
        """
        sanitized = []
        for t in search_tuple:
            if t is None:
                sanitized.append(t)
            else:
                sanitized.append(t.encode('base64'))
        key = simplejson.dumps(sanitized)

        if key in self._cache:
            entry = self._cache[key]
            if int(time()) < entry[0]:
                print "-> Fetching tuple from the cache", entry[1], "TTL:", int(time()) - entry[0], 's'
                return entry[1]

        return None

    def cache_store_tuples(self, search_tuple, result_tuples):
        """
        store the tuple list in our cache
        with an end of life timestamp
        """
        sanitized = []
        for t in search_tuple:
            if t is None:
                sanitized.append(t)
            else:
                sanitized.append(t.encode('base64'))
        key = simplejson.dumps(sanitized)

        lifetime = int(time()) + 10
        self._cache[key] = (lifetime, result_tuples)

_network_handler = None
_dht_df = defer.Deferred()
_dht_df.callback(None)

def set_network_handler(obj):
    """
    set the network handler object.
    should be an instance of the network handler class above
    will be used by all functions below
    """
    print "->", "setting network handler!", obj
    global _network_handler
    _network_handler = obj

    def do_nothing(val):
        print "Doing nothing!"
        return val

    _dht_df.addCallback(do_nothing)


class Plugin(ad3.models.abstract.Plugin):
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
        self.key = key

    def __get_key(self):
        global _network_handler
        return _network_handler.hash_function("plugin_" + self.name + self.module_name)

    def save(self):
        outer_df = defer.Deferred()
        df = defer.Deferred()

        def save_my_tuple(val):
            my_tuple = ("plugin", self.key, self.name, self.module_name)
            df =  _network_handler.dht_store_tuple(my_tuple)
            return df

        def save_value(val):
            my_hash = {'name': self.name,
                       'module_name': self.module_name,
                       'key': self.key.encode('hex'),
                       'type': 'plugin'}
            my_string = simplejson.dumps(my_hash)
            df = _network_handler.dht_store_value(self.key, my_string)
            return df

        def done(val):
            outer_df.callback(val)

        if self.key is None:
            self.key = self.__get_key()
            df.addCallback(save_my_tuple)
            df.addCallback(save_value)

        df.addCallback(done)
        df.callback(None)

        return outer_df

class AudioFile(ad3.models.abstract.AudioFile):
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

    def __get_key(self):
        r = _network_handler.hash_function("audio_file_" + self.file_name + self.user_name)
        return r

    def unsaved_key(self):
        return self.__get_key()

    def save(self):
        outer_df = defer.Deferred()
        df = defer.Deferred()

        def save_my_tuple(val):
            my_tuple = ("audio_file", self.key, self.file_name, self.user_name)
            df = _network_handler.dht_store_tuple(my_tuple)
            return df

        def save_value(val):
            my_hash = {'file_name': self.file_name,
                       'vector': self.vector,
                       'user_name': self.user_name,
                       'key': self.key.encode('hex'),
                       'type': 'audio_file'}
            my_string = simplejson.dumps(my_hash)
            df = _network_handler.dht_store_value(self.key, my_string)
            return df

        def done(val):
            outer_df.callback(val)

        if self.key is None:
            self.key = self.__get_key()
            df.addCallback(save_my_tuple)

        df.addCallback(save_value)
        df.addCallback(done)
        df.callback(None)

        return outer_df

class Tag(ad3.models.abstract.Tag):
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

    def __get_key(self):
        return _network_handler.hash_function("tag_" + self.name)

    def save(self):
        outer_df = defer.Deferred()
        df = defer.Deferred()

        def save_my_tuple(val):
            my_tuple = ("tag", self.key, self.name)
            df = _network_handler.dht_store_tuple(my_tuple)
            return df

        def save_value(val):
            my_hash = {'name': self.name,
                       'vector': self.vector,
                       'key': self.key.encode('hex'),
                       'type': 'tag' }
            my_string = simplejson.dumps(my_hash)
            df = _network_handler.dht_store_value(self.key, my_string)
            return df

        def done(val):
            outer_df.callback(val)

        if self.key is None:
            self.key = self.__get_key()
            df.addCallback(save_my_tuple)

        df.addCallback(save_value)
        df.addCallback(done)
        df.callback(None)

        return outer_df


class PluginOutput(ad3.models.abstract.PluginOutput):
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

    def __get_key(self):
        return _network_handler.hash_function("plugin_output_"+str(self.vector))

    def save(self):
        outer_df = defer.Deferred()
        df = defer.Deferred()

        def done(val):
            outer_df.callback(val)

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
            self.key = self.__get_key()
            # chain our tuple saving procedures, so they don't happen at the same time
            df.addCallback(save_my_tuple)
            df.addCallback(save_plugin_tuple)
            df.addCallback(save_audio_tuple)

        df.addCallback(save_value)
        df.addCallback(done)
        df.callback(None)

        return outer_df



def get_tags(callback, name = None, audio_file = None, guessed_file = None):
    """ Return a list of Tag objects to the provided callback function
    By default returns all tags.

    @param name: return only tags with tag.name matching provided name
    @type  name: unicode

    @param audio_file: return only tags that have been applied to this audio file
    @type  audio_file: AudioFile object

    @param guessed_file: return only tags that have been guessed for this audio file
    @type  guessed_file: AudioFile object

    @param callback: callback function to pass the results to
    @type  callback: function
    """
    search_tuples = [ ("tag", None, name) ]
    if audio_file is not None:
        search_tuples.append( ("tag", None, "audio_file", audio_file.key) )
    if guessed_file is not None:
        search_tuples.append( ("tag", None, "guessed_file", guessed_file.key) )

    return _network_handler.get_objects_matching_tuples(search_tuples, callback)

def get_tag(callback, name):
    """ Returns a single Tag object to the provided callback function.
    If no such Tag exists in the data store, passes None to the callback function.

    @param name: the name of the tag object to return
    @type  name: unicode
    """
    search_tuples = [("tag", None, name)]
    return _network_handler.get_object_matching_tuples(search_tuples, callback)

def get_plugin_outputs(callback, audio_file=None, plugin=None):
    if audio_file is not None:
        audio_key = audio_file.key
    else:
        audio_key = None
    if plugin is not None:
        plugin_key = plugin.key
    else:
        plugin_key = None

    search_tuples = [ ("plugin_output", None, plugin_key, audio_key) ]
    return _network_handler.get_objects_matching_tuples(search_tuples, callback)

def get_plugin_output(callback, audio_file, plugin):
    search_tuples = [ ("plugin_output", None, plugin.key, audio_file.key) ]
    return _network_handler.get_objects_matching_tuples(search_tuples, callback)

def get_plugins(callback, name = None, module_name = None, plugin_output = None):
    """ Return a list of Plugin objects to the provided callback function
    By default returns all plugins.

    @param name: if provided, returns only plugins with a matching name
    @type  name: unicode

    @param module_name: if provided, returns only plugins with a matching module_name
    @type  module_name: unicode

    @param plugin_output: if provided, returns only the plugin associated with this object
    @type  plugin_output: PluginOutput object

    @param callback: a callback function to pass the results to
    @type  callback: function
    """
    search_tuples = [ ("plugin", None, name, module_name) ]
    if plugin_output is not None:
        search_tuples.append( ("plugin", None, "plugin_output", plugin_output.key) )
    return _network_handler.get_objects_matching_tuples(search_tuples, callback)

def get_plugin(callback, name = None, module_name = None, plugin_output = None):
    """ Return a single Plugin object to the provided callback function.

    @param name: if provided, returns only plugins with a matching name
    @type  name: unicode

    @param module_name: if provided, returns only plugins with a matching module_name
    @type  module_name: unicode

    @param plugin_output: if provided, returns only the plugin associated with this object
    @type  plugin_output: PluginOutput object

    @param callback: a callback function to pass the results to
    @type  callback: function
    """
    search_tuples = [ ("plugin", None, name, module_name) ]
    if plugin_output is not None:
        search_tuples.append( ("plugin", None, "plugin_output", plugin_output.key) )
    return _network_handler.get_object_matching_tuples(search_tuples, callback)

def get_audio_files(callback, file_name=None, user_name=None, tag=None, guessed_tag=None, plugin_output=None):
    """ Return a list of AudioFile objects to the provided callback function.
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

    @param callback: a callback function to pass the results to
    @type  callback: function
    """
    search_tuples = [ ("audio_file", None, file_name, user_name) ]
    if tag is not None:
        search_tuples.append( ("audio_file", None, "tag", tag.key) )
    if guessed_tag is not None:
        search_tuples.append( ("audio_file", None, "guessed_tag", guessed_tag.key) )
    if plugin_output is not None:
        search_tuples.append( ("audio_file", None, "plugin_output", plugin_output.key) )

    return _network_handler.get_objects_matching_tuples(search_tuples, callback)

def get_audio_file(callback, file_name=None, user_name=None, tag=None, guessed_tag=None, plugin_output=None):
    """ Return a list of AudioFile objects to the provided callback function.
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

    @param callback: a callback function to pass the results to
    @type  callback: function
    """
    search_tuples = [ ("audio_file", None, file_name, user_name) ]
    if tag is not None:
        search_tuples.append( ("audio_file", None, "tag", tag.key) )
    if guessed_tag is not None:
        search_tuples.append( ("audio_file", None, "guessed_tag", guessed_tag.key) )
    if plugin_output is not None:
        search_tuples.append( ("audio_file", None, "plugin_output", plugin_output.key) )

    return _network_handler.get_object_matching_tuples(search_tuples, callback)


def save(obj):
    """ Save an object to permanent storage.

    @param obj: the object to save
    @type  obj: Saveable
    """
    #print "->", "saving object...", obj
    df = obj.save()
    return df

def update_vector(plugin, audio_file):
    """ Create or Replace the current PluginOutput object for the
    provided plugin/audio file pair. Saves the PluginObject to storage.

    @param plugin: the plugin object to use
    @type  plugin: Plugin

    @param audio_file: the audio file to run the plugin on
    @type  audio_file: AudioFile
    """
    print "------\n -> Beginning update vector"

    # list to store the contact we offloaded to
    # sendOffloadCommand() method updates its value
    struct = {
        'contact': None,
        'module_name': plugin.module_name,
        'file_uri': 'http://127.0.0.1/audio'+ audio_file.file_name,
        'downloaded': False,
        'complete': False,
        'failed': False,
        'vector': None,
        'timestamp': int(time())
    }

    df_chain = defer.Deferred()
    outer_df = defer.Deferred()
    poll_cb = None

    audio_key = audio_file.key

    if audio_key is None:
        # if the file hasn't been saved yet, audio_file.key won't be set
        audio_key = audio_file.unsaved_key()

    def done(val):
        print "Plugin Output Created and Saved. Calling back now.", val
        outer_df.callback(None)

    def save_plugin_output(vector):
        po = PluginOutput(vector, plugin.key, audio_key)
        df = save(po)
        df.addCallback(done)
        return df

    def calculate_vector_yourself(val):
        print "Calculating the damned vector myself"
        vector = plugin.create_vector(str(audio_file.file_name))
        df = save_plugin_output(vector)
        return df

    def error(failure):
        print "Error getting vector from contact. MSG: ", failure.getErrorMessage()
        df = calculate_vector_yourself(None)
        return df

    def polled(val):
        if struct['failed']:
            print "Poll failed"
            df = calculate_vector_yourself(None)
        elif struct['complete'] and not struct['failed']:
            print "Poll complete!"
            df = save_plugin_output(struct['vector'])
        else:
            print "Poll unfinished. sheduling another one"
            # schedule another poll
            df_chain.addCallback(poll_cb)
        return val

    def poll(val):
        if struct['complete']:
            # we're through!
            print "transaction complete!"
            return None
        elif int(time()) - struct['timestamp'] > 45:
            # timed out. just calculate it yourself
            print "Transaction timed out. do it yourself."
            df = calculate_vector_yourself(None)
        else:
            print "POLLING"
            # execute a poll and call the "polled" method when it's done
            df = _network_handler.node.pollOffloadedCalculation(audio_key, struct)
            df.addBoth(polled)

    poll_cb = partial(reactor.callLater, 5, poll)

    def request_accepted(contact):
        print "REQUEST ACCEPTED!!"
        # start the polling loop here.
        df_chain.addCallback(poll_cb)
        df_chain.callback(None)

    def farm_out_vector_calculation():
        print "Attempting to farm out vector calculation"
        df = _network_handler.node.sendOffloadCommand(audio_key, struct)
        return df

    df = farm_out_vector_calculation()

    # best case scenario, farming out the calculation works
    df.addCallback(request_accepted)

    # if farming out calculation fails (eg. times out)
    df.addErrback(error)

    print "-> returning update vector"
    return outer_df

def initialize_storage(callback):
    """ Initializes an empty storage environment.

    For a database, this might mean to (re)create all tables.
    """
    pass

def apply_tag_to_file(audio_file, tag):
    tag_tuple = ("tag", tag.key, "audio_file", audio_file.key)
    audio_tuple = ("audio_file", audio_file.key, "tag", tag.key)

    #print "APPLYING TAG TO FILE:", tag

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

    def done(val):
        outer_df.callback(val)

    def remove_tag_tuples(val):
        tag_tuple = ("tag", None, "guessed_file", None)
        df = _network_handler.dht_remove_tuples(tag_tuple)
        return df

    def remove_audio_tuples(val):
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

    tag_tuple = ("tag", tag.key, "guessed_file", audio_file.key)
    audio_tuple = ("audio_file", audio_file.key, "guessed_tag", tag.key)

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

class MyProtocol(entangled.kademlia.protocol.KademliaProtocol):
    def sendRPC(self, contact, method, args, rawResponse=False):
        print "-->> myprotocol: sendRPC(", contact, ",", method
        outer_df = defer.Deferred()

        def error(failure):
            print "myprotocol: ERROR", failure
            outer_df.errback(failure)
            return failure

        def got_response(val):
            print "myprotocol: GOT RESPONSE", val
            outer_df.callback(val)
            return val

        def actually_send(val):
            print "myprotocol: SENDING (", method, ",", args, ",", rawResponse,")"
            df = KademliaProtocol.sendRPC(self, contact, method, args, rawResponse)
            return df

        # the deferred returned by this is what _dht_df waits for
        # it should get called back as soon as we get a response message
        def handle_dfs(val):
            print "<<---------->>"
            print "myprotocol: HANDLING DFS"
            df = defer.Deferred()
            def done(val):
                print "myprotocol: DONE"
                import time
                time.sleep(0.1)
                print "myprotocol: Continuing..."
                df.callback(None)

            inner_df = defer.Deferred()
            inner_df.addCallback(actually_send)
            inner_df.addCallback(got_response)
            inner_df.addErrback(error)
            inner_df.addBoth(done)
            inner_df.callback(None)

            return df

        # should execute immediately
        _dht_df.addCallback(handle_dfs)

        # should get called back as soon as msg returns.
        print "--<< myprotocol: RETURNING outer_df"
        return outer_df

class MyNode(entangled.dtuple.DistributedTupleSpacePeer):
    def sendOffloadCommand(self, key, struct):
        hash = {
            'module_name': struct['module_name'],
            'file_uri': struct['file_uri']
        }
        value = simplejson.dumps(hash)

        def executeRPC(nodes):
            contact = random.choice(nodes)
            print "SENDING RPC TO:", contact
            struct['contact'] = contact

            df = contact.offload(key, value, self.id)
            return df

        # Find k nodes closest to the key...
        df = self.iterativeFindNode(key)
        df.addCallback(executeRPC)

        return df

    def pollOffloadedCalculation(self, key, struct):
        hash = {
            'module_name': struct['module_name'],
            'file_uri': struct['file_uri']
        }
        value = simplejson.dumps(hash)

        def update_struct(val):
            response = simplejson.loads(val)
            struct['complete'] = response['complete']
            struct['failed'] = response['failed']
            struct['vector'] = response['vector']

        df = struct['contact'].poll(key, value, self.id)
        df.addCallback(update_struct)

        return df

    @rpcmethod
    def offload(self, key, value, originalPublisherID=None, **kwargs):
        print "-------------"
        hash = simplejson.loads(value)

        plugin_module = hash['module_name']
        file_uri = hash['file_uri']
        id = plugin_module + file_uri
        print "RECEIVED AN OFFLOAD RPC!", file_uri, plugin_module

        if not hasattr(self, 'computations'):
            self.computations = {}

        self.computations[id] = {
            'complete': False,
            'vector': None,
            'failed': False,
            'downloaded': False
        }

        def do_computation():
            try:
                plugin = Plugin('temp', plugin_module)

                print "Downloading", file_uri
                (file_name, headers) = urllib.urlretrieve('http://'+urllib.quote(file_uri[7:]))
                self.computations[id]['downloaded'] = True

                print "Computing vector for", file_name
                vector = plugin.create_vector(file_name)
                self.computations[id]['complete'] = True
                self.computations[id]['vector'] = vector

                os.remove(file_name)
            except Exception:
                print "Computation error :(", failure.getErrorMessage()
                self.computations[id]['complete'] = True
                self.computations[id]['failed'] = True
            finally:
                return None

        from twisted.internet import threads
        df = threads.deferToThread(do_computation)

        #file = tempfile.NamedTemporaryFile(suffix=key.encode('hex'))
        #file.write(value)
        print "OFFLOAD FINISHED"
        return "OK"

    @rpcmethod
    def poll(self, key, value, originalPublisherID=None, age=0, **kwargs):
        hash = simplejson.loads(value)
        plugin_module = hash['module_name']
        file_uri = hash['file_uri']
        id = plugin_module + file_uri

        if not hasattr(self, 'computations') or not self.computations.has_key(id):
            # we've never heard of the requested offload operation. make something up!
            print "Returning BS poll"
            result = {'complete': True, 'vector': None, 'failed': True, 'downloaded': False}
        elif self.computations[id]['complete']:
            # we've finished the requested offload operation. remove if from the list and return it
            print "Returning finished poll"
            result = self.computations.pop(id)
        else:
            # we haven't finished the requested offload operation, but we have some data on it
            print "Returning unfinished poll"
            result = self.computations[id]

        return simplejson.dumps(result)
