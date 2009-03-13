from numpy import mean, array, dot, sqrt, subtract

# FIXME: this should be defined elsewhere
def euclidean_distance(a, b):
    """
    takes two numpy arrays, a, b, both of length n
    returns the magnitude of the distance between them (float)
    """
    c = subtract(a,b)
    sum_of_squares = dot(c,c)
    return sqrt(sum_of_squares)

class Euclidean(object):
    def __init__(self, data_model, tolerable_distance = 200):
        self.model = data_model
        self.tolerance = tolerable_distance


    def calculate_tag_vector(self, callback, tag):
        def got_files(files):
            vector = mean([f.vector for f in files], axis=0).tolist()
            callback(vector)

        return self.model.get_audio_files(got_files, tag = tag)


    def calculate_file_vector(self, callback, file):
        def got_outputs(pos):
            vector = []
            for po in pos:
                vector.extend(po.vector)
            callback(vector)
        return self.model.get_plugin_outputs(got_outputs, audio_file=file)


    def does_tag_match(self, callback, file, tag):
        if euclidean_distance(tag.vector, file.vector) <= self.tolerance:
            return True
        return False

