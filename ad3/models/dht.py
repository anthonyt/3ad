import ad3.models.abstract
import simplejson
from time import time

class TupleAggregator(object):
    def __init__(self, net_handler, tuple_list):
        self.net_handler = net_handler
        self.tuple_list = tuple_list
        self.tuple_count = len(tuple_list)
        self.objects = []

    def go(self, callback):
        def got_value(value):
            # append this value to our list
            obj = self.net_handler.obj_from_row(value)
            self.objects.append(obj)

            # if we have got all the values we asked for
            # call the callback function
            if len(self.objects) == len (self.tuple_list):
                callback(self.objects)

        # for each tuple, try to fetch a cached version of the object
        # otherwise run our got_value function on the value row
        for t in self.tuple_list:
            cached = self.net_handler.cache_get_obj(t[0])
            if cached is not None:
                self.objects.append(cached)
            else:
                self.net_handler.dht_get_value(t[0], got_value)

class NetworkHandler(object):
    def __init__(self, node)
        self.node = node
        self._cache = {}

    def obj_from_row(self, row):
        pass

    def hash_function(self, plain_key):
        h = hashlib.sha1()
        h.update(plain_key)
        return h.digest()

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

    def dht_get_value(self, key, callback):
        def success(result):
            if type(result) == dict:
                value = result[key]
            else:
                value = None

            callback(value)

        def error(failure):
            print 'An error occurred:', failure.getErrorMessage()
            callback(None)

        df = self.node.iterativeFindValue(key)
        df.addCallback(success)
        df.addErrback(error)

    def dht_store_value(self, key, value):
        def success(result):
            print 'stored value:', result

        df = self.node.iterativeStore(key, value)
        df.addCallback(success)

    def dht_get_tuples(self, dTuple, callback)
        def success(result):
            """
            @type result  tuple or None
            """
            callback(result)

        def error(failure):
            print 'an error occurred:', failure.getErrorMessage()
            callback(None)

        df = self.node.readIfExists(template, 0)
        df.addCallback(success)
        df.addErrback(error)

    def dht_store_tuple(self, dTuple):
        def success(result):
            print 'stored tuple:', result

        df = self.node.put(dTuple)
        df.addCallback(success)

    def get_tags(self, name = None, callback = None):
        """ Return a list of Tag objects. By default returns all tags.

        @param name: return only tags with tag.name matching provided name
        @type  name: unicode
        """
        def got_tuples(result):
            if result is None:
                callback([])
            else:
                # if we actually have tuples returned
                # call our tuple agregator to find corresponding value rows
                ta = TupleAggregator(self, result)
                ta.go(callback)

        # get a list of all tags in the DHT
        self.dht_get_tuples( ("tag", None, name), got_tuples )

    def get_tag(self, name, callback = None):
        """ Returns a single Tag object with the provided name.

        If no existing tag is found, a new one is created and returned.

        @param name: the name of the tag object to return
        @type  name: unicode
        """
        pass

    def initialize_storage(self, callback = None):
        """ Initializes an empty storage environment.

        For a database, this might mean to (re)create all tables.
        """
        pass

    def fetch_plugin_output(self, key, callback = None):
        my_string = get_value(key)
        my_hash = simplejson.decode(my_string)
        return PluginOutput(my_hash['

    def fetch_plugin(self, key, callback = None):
        my_string = get_value(key)
        my_hash = simplejson.decode(my_string)
        return Plugin(my_hash['name'], my_hash['module_name'], key)

    def get_plugins(self, name = None, module_name = None, callback = None):
        """ Return a list of Plugin objects. By default returns all plugins.

        @param name: if provided, returns only plugins with a matching name
        @type  name: unicode

        @param module_name: if provided, returns only plugins with a matching module_name
        @type  module_name: unicode
        """
        plugin_tuples = self.dht_get_tuple(("plugin", None, name, module_name))
        plugin_objects = [fetch_plugin(t[1]) for t in plugin_tuples]
        return plugin_objects

    def get_audio_files(self, file_name=None, tag_names=None, include_guessed=False, callback = None):
        """ Return a list of AudioFile objects. By default returns all audio files.

        @param file_name: if provided, returns only files with a matching file name
        @type  file_name: unicode

        @param tag_names: if provided, returns only files with at least one of the provided tags
        @type  tag_names: list of unicode objects

        @param include_guessed: if provided, when looking for matching tags, includes generated_tags in the search
        @type  include_guessed: bool
        """
        pass

    def get_audio_file(self, file_name, callback = None):
        """ Return an AudioFile object. If no existing object is found, returns None.

        @param file_name: the file name of the audio file
        @type  file_name: unicode
        """
        pass

    def save(self, obj, callback = None):
        """ Save an object to permanent storage.

        @param obj: the object to save
        @type  obj: Saveable
        """
        pass

    def update_vector(self, plugin, audio_file, callback = None):
        """ Create or Replace the current PluginOutput object for the
        provided plugin/audio file pair. Saves the PluginObject to storage.

        @param plugin: the plugin object to use
        @type  plugin: Plugin

        @param audio_file: the audio file to run the plugin on
        @type  audio_file: AudioFile
        """
        pass


__network_handler = None

def set_network_handler(obj):
    """
    set the network handler object.
    should be an instance of the network handler class above
    will be used by all functions below
    """
    __network_handler = obj

class Plugin(ad3.models.abstract.Plugin):
    """
    Plugin Object

    Attributes:
        name
        module_name
        outputs
        key

    Methods:
        create_vector(audiofile)
        save()
    """

    def __init__(self, name, module_name, key = None):
        ad3.models.abstract.Plugin.__init__(self, name, module_name)
        self.key = key
        if key = None:
            self.outputs = []
        else:
            self.outputs = 

    def create_vector(self, audiofile):
        return PluginOutput(self.module.createVector(audiofile.file_name), self, audiofile)

    def __get_key(self):
        return hash_function("plugin_" + self.name + self.module_name)

    def save(self):
        if self.key is None:
            self.key = self.__get_key()

        my_hash = {'name': self.name, 'module_name': self.module_name}
        my_tuple = ("plugin", self.key, self.name, self.module_name)
        my_string = simplejson.encode(my_hash)

        store_value(self.key, my_string)
        put_tuple(my_tuple)
"""
to save a plugin:
    key = hash_function("plugin_" + plugin_name + module_name)
    tuple = ("plugin", key, plugin.name, plugin.module_name)
    plugin_value = simplejson.encode({ 'name': plugin.name, 'module_name': plugin.module_name })

    self.storeValue(key, plugin_value)
    self.putTuple(self, dTuple)

to fetch a single plugin given a key:
    p = self.getValue(key)
    p = simplejson.decode(p)
    return Plugin(p['name'], p['module_name'], key)


to fetch a list of all plugins:
    l = self.readTuple(("plugin", key, None, None))
    ps = [fetch_single_plugin(t[1]) for t in l]

to fetch all PluginOutputs associated with a plugin:
    l = self.readTuple(("plugin_output", None, plugin.key, None))
    pos = [fetch_single_plugin_output(t[1]), for t in l]
"""

class AudioFile(ad3.models.abstract.AudioFile):
    """
    Audio File Object

    Attributes:
        name
        vector
        tags
        generated_tags
        id

    Method:
        getKey
    """

    def __init__(self, file_name, id = None):
        ad3.models.abstract.AudioFile.__init__(self, file_name)
        id = id

class Tag(ad3.models.abstract.Tag):
    """
    Tag Object

    Attributes:
        name
        files
        vector
    """

    def __init__(self, name):
        self.name = name
        self.vector = []


class PluginOutput(ad3.models.abstract.PluginOutput):
    """
    Object to represent the output of a plugin

    Attributes:
        vector
        plugin
        file
    """

    def __init__(self, vector, plugin, audiofile):
        self.vector = vector
        self.plugin = plugin
        self.file = audiofile

    def __repr__(self):
        return "<PluginOutput('%s')>" % (self.vector)


def get_tags(name = None, callback = None):
    """ Return a list of Tag objects. By default returns all tags.

    @param name: return only tags with tag.name matching provided name
    @type  name: unicode
    """
    return __network_handler.get_tags(name, callback)

def get_tag(name, callback = None):
    """ Returns a single Tag object with the provided name.

    If no existing tag is found, a new one is created and returned.

    @param name: the name of the tag object to return
    @type  name: unicode
    """
    return __network_handler.get_tags(name, callback)

def initialize_storage(callback = None):
    """ Initializes an empty storage environment.

    For a database, this might mean to (re)create all tables.
    """
    return __network_handler.initialize_storage(callback)

def get_plugins(name = None, module_name = None, callback = None):
    """ Return a list of Plugin objects. By default returns all plugins.

    @param name: if provided, returns only plugins with a matching name
    @type  name: unicode

    @param module_name: if provided, returns only plugins with a matching module_name
    @type  module_name: unicode
    """
    return __network_handler.get_plugins(name, module_name, callback)

def get_audio_files(file_name=None, tag_names=None, include_guessed=False, callback = None):
    """ Return a list of AudioFile objects. By default returns all audio files.

    @param file_name: if provided, returns only files with a matching file name
    @type  file_name: unicode

    @param tag_names: if provided, returns only files with at least one of the provided tags
    @type  tag_names: list of unicode objects

    @param include_guessed: if provided, when looking for matching tags, includes generated_tags in the search
    @type  include_guessed: bool
    """
    return __network_handler.get_audio_files(file_name, tag_names, include_guessed, callback)

def get_audio_file(file_name, callback = None):
    """ Return an AudioFile object. If no existing object is found, returns None.

    @param file_name: the file name of the audio file
    @type  file_name: unicode
    """
    return __network_handler.get_audio_file(file_name, callback)

def save(obj, callback = None):
    """ Save an object to permanent storage.

    @param obj: the object to save
    @type  obj: Saveable
    """
    return __network_handler.save(obj, callback)

def update_vector(plugin, audio_file, callback = None):
    """ Create or Replace the current PluginOutput object for the
    provided plugin/audio file pair. Saves the PluginObject to storage.

    @param plugin: the plugin object to use
    @type  plugin: Plugin

    @param audio_file: the audio file to run the plugin on
    @type  audio_file: AudioFile
    """
    return __network_handler.update_vector(plugin, audio_file, callback)

