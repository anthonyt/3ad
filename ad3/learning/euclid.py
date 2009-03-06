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

    def calculate_tag_vector(self, tag):
        files = self.model.get_audio_files(tag_names = [tag.name])
        vector = mean([f.vector for f in files], axis=0).tolist()
        return vector

    def calculate_file_vector(self, file):
        vector = []
        for po in file.outputs:
            vector.extend(po.vector)
        return vector

    def does_tag_match(self, file_name, tag_name):
        files = self.model.get_audio_files(file_name = file_name, tag_names = [tag_name])
        tags = self.model.get_tags(tag_name)

        # there should only be one tag and one file, maximum
        for tag in tags:
            for file in files:
                if euclidean_distance(tag.vector, file.vector) <= self.tolerance:
                    return True
        return False

