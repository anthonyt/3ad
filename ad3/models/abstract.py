
class Plugin(object):
    """
    Plugin Object

    Attributes:
        name
        module_name
        outputs

    Methods:
        createVector
    """

    def __init__(self, name, module_name):
        self.name = name
        self.module_name = module_name
        self.outputs = []

    def __getattr__(self, name):
        if name == "module":
            # Lazy load the plugin module
            if "module" not in self.__dict__:
                mod = __import__(self.module_name)
                components = self.module_name.split('.')
                for comp in components[1:]:
                    mod = getattr(mod, comp)
                self.__dict__["module"] = mod
            return self.__dict__["module"]
        else:
            return object.__getattr__(name)


    def __repr__(self):
        return "<Plugin('%s','%s')>" % (self.name, self.module_name)

    def create_vector(self, file_name):
        return self.module.createVector(file_name)


class AudioFile(object):
    """
    Audio File Object

    Attributes:
        name
        vector
    """

    def __init__(self, file_name):
        self.file_name = file_name
        self.vector = []

    def __repr__(self):
        return "<AudioFile('%s')>" % (self.file_name)


class Tag(object):
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

    def __repr__(self):
        return "<Tag('%s')>" % (self.name)


class PluginOutput(object):
    """
    Object to represent the output of a plugin

    Attributes:
        vector
        plugin
        file
    """

    def __init__(self, vector):
        self.vector = vector

    def __repr__(self):
        return "<PluginOutput('%s')>" % (self.vector)


def get_tags(name = None):
    """ Return a list of Tag objects. By default returns all tags.

    @param name: return only tags with tag.name matching provided name
    @type  name: unicode
    """
    pass

def get_tag(name):
    """ Returns a single Tag object with the provided name, if one exists in the data store.

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

