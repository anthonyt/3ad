import ad3.models.abstract
import simplejson
import hashlib
from time import time
from sets import Set

class KeyAggregator(object):
    # Once initialized with a list of tuples to match against
    def __init__(self, net_handler, tuple_list):
        self.net_handler = net_handler
        self.tuple_list = tuple_list
        self.key_lists = []

    def go(self, callback):
        def got_tuples(tuples):
            if tuples is None:
                # not sure if this is necessary
                # depends what get_tuples() returns (below)
                keys = []
            else:
                keys = [t[1] for t in tuples]

            self.key_lists.append(keys)

            # if we have got all the values we asked for,
            # find the common keys, and call the callback function
            if len(self.key_lists) == len(self.tuple_list):
                keys = Set(self.key_lists[0])

                for ks in self.key_lists[1:]:
                    keys = keys.intersection(ks)

                callback(list(keys))

        # for each search tuple, run our got_tuples function on the resulting tuple rows
        for dTuple in self.tuple_list:
            self.net_handler.dht_get_tuples(dTuple, got_tuples)


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
            print "Searching for key..", key
            self.net_handler.dht_get_value(key, got_value)


class NetworkHandler(object):
    def __init__(self, node):
        self.node = node
        self._cache = {}

    def obj_from_row(self, row):
        print "OBJ FROM ROW", row
        h = simplejson.loads(row)

        if h['type'] == "plugin":
            o = Plugin(h['name'], h['module_name'], h['key'].decode('hex'))

        elif h['type'] == "plugin_output":
            o = PluginOutput(h['vector'], h['plugin_key'], h['audio_key'], h['key'].decode('hex'))

        elif h['type'] == "tag":
            o = Tag(h['name'], h['vector'], h['key'].decode('hex'))

        elif h['type'] == "audio_file":
            o = AudioFile(h['file_name'], h['vector'], h['key'].decode('hex'))

        else:
            o = None

        return o


    def hash_function(self, plain_key):
        print "HASHING!"
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
            print 'An error occurred:', failure.getErrorMessage()
            callback(None)

        df = self.node.iterativeFindValue(key)
        # use the "success" function to filter our result before
        # passing it to the callback
        df.addCallback(success)
        df.addCallback(callback)
        df.addErrback(error)


    def dht_store_value(self, key, value):
        def success(result):
            print 'stored value:', result

        df = self.node.iterativeStore(key, value)
        df.addCallback(success)


    def dht_get_tuples(self, dTuple, callback):
        def success(result):
            """
            @type result  tuple or None
            """
            callback(result)

        def error(failure):
            print 'an error occurred:', failure.getErrorMessage()
            callback(None)

        print "searching for tuples based on", dTuple
        df = self.node.readIfExists(dTuple, 0)
        df.addCallback(success)
#        df.addErrback(error)

    def dht_store_tuple(self, dTuple):
        def success(result):
            print 'stored tuple:', result

        def error(failure):
            print 'an error occurred:', failure.getErrorMessage()

        print "Attempting to store tuple:", dTuple
        df = self.node.put(dTuple)
        df.addCallback(success)
        df.addErrback(error)


    def get_objects_matching_tuples(self, tuple_list, callback):
        """
        Return a list of the appropriate objects for each object row
        that matches all of the provided search tuples in the tuple_list

        NB: providing an empty tuple list will result in no callback being fired
        """
        def got_keys(keys):
            if len(keys) == 0:
                callback([])
            else:
                # if we actually have keys returned
                # call our tuple agregator to find corresponding value rows
                ta = ObjectAggregator(self, keys)
                ta.go(callback)

        print "Making a KA object with tuple list:", tuple_list
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
                return entry[1]

        return None

    def cache_store_obj(self, key, obj):
        """
        store the object in our cache
        with an end of life timestamp
        """
        lifetime = int(time()) + 30
        self._cache[key] = (lifetime, obj)

_network_handler = None

def set_network_handler(obj):
    """
    set the network handler object.
    should be an instance of the network handler class above
    will be used by all functions below
    """
    print "setting network handler!", obj
    global _network_handler
    _network_handler = obj

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
        if self.key is None:
            self.key = self.__get_key()

            my_hash = {'name': self.name,
                       'module_name': self.module_name,
                       'key': self.key.encode('hex'),
                       'type': 'plugin'}
            my_string = simplejson.dumps(my_hash)
            _network_handler.dht_store_value(self.key, my_string)

            my_tuple = ("plugin", self.key, self.name, self.module_name)
            _network_handler.dht_store_tuple(my_tuple)

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

    def __init__(self, file_name, vector = None, key = None):
        ad3.models.abstract.AudioFile.__init__(self, file_name)

        self.vector = vector
        self.key = key

    def __get_key(self):
        print "getting key..."
        r = _network_handler.hash_function("audio_file_" + self.file_name)
        print "got key"
        print r
        return r

    def save(self):
        print "I'm IN"
        if self.key is None:
            self.key = self.__get_key()
            print "Setting key for the first time...", self.key

            my_tuple = ("audio_file", self.key, self.file_name)
            _network_handler.dht_store_tuple(my_tuple)

        my_hash = {'file_name': self.file_name,
                   'vector': self.vector,
                   'key': self.key.encode('hex'),
                   'type': 'audio_file'}
        my_string = simplejson.dumps(my_hash)
        _network_handler.dht_store_value(self.key, my_string)

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
        if self.key is None:
            self.key = self.__get_key()

            my_tuple = ("tag", self.key, self.name)
            _network_handler.dht_store_tuple(my_tuple)

        my_hash = {'name': self.name,
                   'vector': self.vector,
                   'key': self.key.encode('hex'),
                   'type': 'tag' }
        my_string = simplejson.dumps(my_hash)
        _network_handler.dht_store_value(self.key, my_string)


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
        if self.key is None:
            self.key = self.__get_key()

            # store a plugin_output row
            my_tuple = ("plugin_output", self.key, self.plugin_key, self.audio_key)
            _network_handler.dht_store_tuple(my_tuple)

            # make a plugin row for cross referencing
            plugin_tuple = ("plugin", self.plugin_key, "plugin_output", self.key)
            _network_handler.dht_store_tuple(plugin_tuple)

            # make an audio_file row for cross referencing
            audio_tuple = ("audio_file", self.audio_key, "plugin_output", self.key)
            _network_handler.dht_store_tuple(audio_tuple)

        # store the object state
        my_hash = {'vector': self.vector,
                   'key': self.key.encode('hex'),
                   'plugin_key': self.plugin_key,
                   'audio_key': self.audio_key,
                   'type': 'plugin_output'}
        my_string = simplejson.dumps(my_hash)
        _network_handler.dht_store_value(self.key, my_string)



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

def get_plugin_outputs(callack, audio_file=None, plugin=None):
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

def get_audio_files(callback, file_name=None, tag=None, guessed_tag=None, plugin_output=None):
    """ Return a list of AudioFile objects to the provided callback function.
    By default returns all audio files.

    @param file_name: if provided, returns only files with a matching file name
    @type  file_name: unicode

    @param tag: if provided, returns only files manually tagged with the provided tag
    @type  tag: Tag object

    @param guessed_tag: if provided, returns only files automatically tagged with the provided tag
    @type  guessed_tag: Tag object

    @param plugin_output: if provided, returns only the file associated with this output
    @type  plugin_output: PluginOutput object

    @param callback: a callback function to pass the results to
    @type  callback: function
    """
    search_tuples = [ ("audio_file", None, file_name) ]
    if tag is not None:
        search_tuples.append( ("audio_file", None, "tag", tag.key) )
    if guessed_tag is not None:
        search_tuples.append( ("audio_file", None, "guessed_tag", guessed_tag.key) )
    if plugin_output is not None:
        search_tuples.append( ("audio_file", None, "plugin_output", plugin_output.key) )

    return _network_handler.get_objects_matching_tuples(search_tuples, callback)

def get_audio_file(callback, file_name=None, tag=None, guessed_tag=None, plugin_output=None):
    """ Return a list of AudioFile objects to the provided callback function.
    By default returns all audio files.

    @param file_name: if provided, returns only files with a matching file name
    @type  file_name: unicode

    @param tag: if provided, returns only files manually tagged with the provided tag
    @type  tag: Tag object

    @param guessed_tag: if provided, returns only files automatically tagged with the provided tag
    @type  guessed_tag: Tag object

    @param plugin_output: if provided, returns only the file associated with this output
    @type  plugin_output: PluginOutput object

    @param callback: a callback function to pass the results to
    @type  callback: function
    """
    search_tuples = [ ("audio_file", None, file_name) ]
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
    print "saving object...", obj
    obj.save()

def update_vector(callback, plugin, audio_file):
    """ Create or Replace the current PluginOutput object for the
    provided plugin/audio file pair. Saves the PluginObject to storage.

    @param plugin: the plugin object to use
    @type  plugin: Plugin

    @param audio_file: the audio file to run the plugin on
    @type  audio_file: AudioFile
    """
    vector = plugin.create_vector(audio_file.name)
    po = PluginOutput(vector, plugin.key, audio_file.key)
    save(po)

def initialize_storage(callback):
    """ Initializes an empty storage environment.

    For a database, this might mean to (re)create all tables.
    """
    pass

def apply_tag_to_file(audio_file, tag):
    tag_tuple = ("tag", tag.key, "audio_file", audio_file.key)
    audio_tuple = ("audio_file", audio_file.key, "tag", tag.key)

    # beware. i'm not sure if the framework will actually detect duplicate tuples
    # you might have to ensure uniqueness before publishing the tuples.
    _network_handler.dht_store_tuple(tag_tuple)
    _network_handler.dht_store_tuple(audio_tuple)


def guess_tag_for_file(audio_file, tag):
    tag_tuple = ("tag", tag.key, "guessed_file", audio_file.key)
    audio_tuple = ("audio_file", audio_file.key, "guessed_tag", tag.key)

    # beware. i'm not sure if the framework will actually detect duplicate tuples
    # you might have to ensure uniqueness before publishing the tuples.
    _network_handler.dht_store_tuple(tag_tuple)
    _network_handler.dht_store_tuple(audio_tuple)

