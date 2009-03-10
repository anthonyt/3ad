import ad3.models.abstract
import simplejson

"""
plugin
	has many: output_vectors

output_vector
	has one: audio_file
	has one: plugin

tag
	has many: audio_file
	fields:
		vector

audio_file
	has many: output_vector
	has many: tag (user_tag)
	has many: tag (auto_tag)
	fields:
		vector
"""

__controller_node = None

def set_node(node):
    __controller_node = node

def hash_function(key):
    h = hashlib.sha1()
    h.update(key)
    return h.digest()

def get_value(hKey):
    def showValue(result):
        if type(result) == dict:
            value = result[hKey]
        if type(value) != str:
            value = '%s: %s' % (type(value), str(value))
        else:
            value = '---not found---'
    def error(failure):
        print 'An error occurred:', failure.getErrorMessage()
    df = __controller_node.iterativeFindValue(hKey)
    df.addCallback(showValue)
    df.addErrback(error)

def store_value(key, value):
    def completed(result):
        print 'stored value:', result

    df = __controller_node.iterativeStore(hKey, value)
    df.addCallback(completed)


def put_tuple(dTuple):
    def completed(result):
        print 'stored tuple:', result

    df = __controller_node.put(dTuple)
    df.addCallback(completed)

def read_tuple(dTuple)
    def showValue(result):
        print 'retrieved tuple:', result

    def error(failure):
        print 'GUI: an error occurred:', failure.getErrorMessage()

    df = __controller_node.readIfExists(template)
    df.addCallback(showValue)
    df.addErrback(error)



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
    return Plugin(p['name'], p['module_name'])


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


def get_tags(name = None):
    """ Return a list of Tag objects. By default returns all tags.

    @param name: return only tags with tag.name matching provided name
    @type  name: unicode
    """
    pass

def get_tag(name):
    """ Returns a single Tag object with the provided name.

    If no existing tag is found, a new one is created and returned.

    @param name: the name of the tag object to return
    @type  name: unicode
    """
    pass

def initialize_storage():
    """ Initializes an empty storage environment.

    For a database, this might mean to (re)create all tables.
    """
    pass

def get_plugins(name = None, module_name = None):
    """ Return a list of Plugin objects. By default returns all plugins.

    @param name: if provided, returns only plugins with a matching name
    @type  name: unicode

    @param module_name: if provided, returns only plugins with a matching module_name
    @type  module_name: unicode
    """
    pass

def get_audio_files(file_name=None, tag_names=None, include_guessed=False):
    """ Return a list of AudioFile objects. By default returns all audio files.

    @param file_name: if provided, returns only files with a matching file name
    @type  file_name: unicode

    @param tag_names: if provided, returns only files with at least one of the provided tags
    @type  tag_names: list of unicode objects

    @param include_guessed: if provided, when looking for matching tags, includes generated_tags in the search
    @type  include_guessed: bool
    """
    pass

def get_audio_file(file_name):
    """ Return an AudioFile object. If no existing object is found, returns None.

    @param file_name: the file name of the audio file
    @type  file_name: unicode
    """
    pass

def save(obj):
    """ Save an object to permanent storage.

    @param obj: the object to save
    @type  obj: Saveable
    """
    pass

def update_vector(plugin, audio_file):
    """ Create or Replace the current PluginOutput object for the
    provided plugin/audio file pair. Saves the PluginObject to storage.

    @param plugin: the plugin object to use
    @type  plugin: Plugin

    @param audio_file: the audio file to run the plugin on
    @type  audio_file: AudioFile
    """
    pass

