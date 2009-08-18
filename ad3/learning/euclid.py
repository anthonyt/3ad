from numpy import mean, array, dot, sqrt, subtract, zeros, copy
from twisted.internet import defer
from .. import logs
logger = logs.logger

def euclidean_distance(a, b):
    """
    takes two numpy arrays, a, b, both of length n
    returns the magnitude of the distance between them (float)
    """
    c = subtract(a,b)
    sum_of_squares = dot(c,c)
    return sqrt(sum_of_squares)

class Euclidean(object):
    def __init__(self, data_model, tolerable_distance = 15):
        self.model = data_model
        self.tolerance = tolerable_distance


    def calculate_tag_vector(self, tag):
        def got_files(files):
            vector = mean([f.vector for f in files], axis=0).tolist()
            return vector

        df = self.model.get_audio_files(tag = tag)
        df.addCallback(got_files)
        return df


    def calculate_file_vector(self, file):
        def got_outputs(plugin_outputs):
            c = lambda a, b: cmp(a.plugin_key, b.plugin_key)
            vector = []
            # sort the plugin_outputs by plugin key.
            for po in sorted(plugin_outputs, c):
                vector.extend(po.vector)
            return vector

        df = self.model.get_plugin_outputs(audio_file=file)
        df.addCallback(got_outputs)
        return df


    def does_tag_match(self, file, tag):
        distance = euclidean_distance(tag.vector, file.vector)
        logger.debug("DISTANCE: %r %r %r", distance, file, tag)
        if distance <= self.tolerance:
            return True
        return False

