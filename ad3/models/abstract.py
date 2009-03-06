
class Plugin(object):
    def __init__(self, name, module_name):
        self.name = name
        self.module_name = module_name

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

    def findMaxDistanceFromAverage(self):
        vecs = [o.vector for o in self.outputs]
        avg = mean(vecs, axis=0)
        distances = [euclidean_distance(v, avg) for v in vecs]
        return max(distances)

    def findMinDistanceFromAverage(self):
        vecs = [array(o.vector) for o in self.outputs]
        avg = mean(vecs, axis=0)
        distances = [euclidean_distance(v, avg) for v in vecs]
        return min(distances)

    def createVector(self, audiofile):
        return PluginOutput(self.module.createVector(audiofile.file_name), self, audiofile)


class AudioFile(object):
    def __init__(self, file_name):
        self.file_name = file_name
        self.vector = []

    def __repr__(self):
        return "<AudioFile('%s')>" % (self.file_name)


class Tag(object):
    def __init__(self, name):
        self.name = name
        self.vector = []

    def __repr__(self):
        return "<Tag('%s')>" % (self.name)


class PluginOutput(object):
    def __init__(self, vector, plugin, audiofile):
        self.vector = vector
        self.plugin = plugin
        self.file = audiofile

    def __repr__(self):
        return "<PluginOutput('%s')>" % (self.vector)


