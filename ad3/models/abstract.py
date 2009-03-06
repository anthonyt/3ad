
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

    def createVector(self, audiofile):
        return PluginOutput(self.module.createVector(audiofile.file_name), self, audiofile)


class AudioFile(object):
    """
    Audio File Object

    Attributes:
        name
        vector
        tags
    """

    def __init__(self, file_name):
        self.file_name = file_name
        self.vector = []
        self.tags = []

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

    def __init__(self, vector, plugin, audiofile):
        self.vector = vector
        self.plugin = plugin
        self.file = audiofile

    def __repr__(self):
        return "<PluginOutput('%s')>" % (self.vector)


