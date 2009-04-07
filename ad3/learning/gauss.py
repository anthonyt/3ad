from numpy import mean, array, dot, sqrt, subtract, zeros, copy
from twisted.internet import defer
from marsyas import *
import zlib

class Gaussian(object):
    def __init__(self, data_model, tolerable_distance = 100):
        self.model = data_model
        self.tolerance = tolerable_distance


    def calculate_tag_vector(self, callback, tag):
        outer_df = defer.Deferred()
        outer_df.addCallback(callback)

        def got_files(files):
            vectors = [f.vector for f in files]
            tag_vector = train(vectors)
            outer_df.callback(tag_vector)

        self.model.get_audio_files(got_files, tag = tag)

        return outer_df


    def calculate_file_vector(self, file):
        print "Calculating File Vector!"
        outer_df = defer.Deferred()

        def got_outputs(plugin_outputs):
            vector = []
            for po in plugin_outputs:
                vector.extend(po.vector)
            outer_df.callback(vector)

        self.model.get_plugin_outputs(got_outputs, audio_file=file)

        return outer_df


    def does_tag_match(self, file, tag):
        data = [file.vector]
        distances = predict(data, tag.vector)
        print "DISTANCE:", distances[0], file, tag
        return (distances[0] <= self.tolerance)


# some more useful function names
mng = MarSystemManager()
fstr = MarControlPtr.from_string
fnat = MarControlPtr.from_natural
freal = MarControlPtr.from_real
fbool = MarControlPtr.from_bool
frvec = MarControlPtr.from_realvec

def list_to_realvec(matrix, cols):
    """
    Takes a two dimensional list (MxN matrix) and the number of columns.
    Returns a realvec object.
    Normally you can tell the column size from looking at the length of
    the first row, but it's possible to have no rows.
    """
    rows = len(matrix)
    vec = realvec(rows, cols)
    for i in range(0, rows):
        for j in range(0, cols):
            vec[j*rows+i] = matrix[i][j]
    return vec

def realvec_to_list(vec):
    """
    Convert a realvec object to a list object.
    Returns a list object along with the number of columns in the
    realvec object.
    Normally you can tell the column size from looking at the length of
    the first row, but it's possible to have no rows.
    """
    rows = vec.getRows()
    cols = vec.getCols()
    arr = zeros((rows, cols))
    for i in range(0, rows):
        for j in range(0, cols):
            arr[i][j] = vec[j*rows + i]
    return (arr.tolist(), cols)

def prepare_data(data):
    """
    Prepares a list of vectors for use by a classifier.
    Classifiers expect each vector in the list to be appended with a 0
    Classifiers also expect the list of vectors to be a realvec object.
    Finally, the expect the realvec object to be transposed, so that rows
    become columns.
    """
    d = copy(data).tolist()
    for v in d:
        v.append(0)
    rv = list_to_realvec(d, len(d[0]))
    rv.transpose()
    return rv


def train(data):
    """
    Takes as input a list of file vectors representative of files with a particular tag.
    Trains a Gaussian classifier to detect vectors matching that tag.
    Returns a gzipped serialization of that classifier.
    """
    data = prepare_data(data)
    net = mng.create("Series", "net")

    # Start setting up our MarSystems
    rv = mng.create("RealvecSource", "rv")
    cl = mng.create("Classifier", "cl")
    net.addMarSystem(rv)
    net.addMarSystem(cl)

    # Set up the appropriate classifier
    net.updControl('Classifier/cl/mrs_string/enableChild', fstr('GaussianClassifier/gaussiancl'))

    # Set up the number of input samples to the system.
    # Don't know what this is for but we need it.
    net.updControl("mrs_natural/inSamples", fnat(1))

    net.updControl("RealvecSource/rv/mrs_realvec/data", frvec(data))

    # Set up the Classifier system
    net.updControl("Classifier/cl/mrs_natural/nClasses", fnat(1))

    # Loop over all the input, ticking the system, and updating the Classifier Mode
    net.updControl("Classifier/cl/mrs_string/mode", fstr("train"))
    while not net.getControl("RealvecSource/rv/mrs_bool/done").to_bool():
        net.tick()

    # Take the system out of training mode, and tick it once to save its state
    net.updControl("Classifier/cl/mrs_string/mode", fstr("predict"))
    net.tick()

    # Separate the classifier system and serialize it
    cl.setParent(None)
    cl.updControl("mrs_bool/active", fbool(False))
    cl_str = cl.toString()
    return zlib.compress(cl_str).encode('base64')


def predict(data, classifier_string):
    """
    Takes as input a list of file vectors, and a serialized Gaussian classifier.
    The Gaussian Classifier should be a classifier for a single tag.
    Returns a list of True/False predictions, one for each input vector.
    """
    data = prepare_data(data)

    # create up our series system
    net = mng.create("Series", "net")

    # Un-serialize the Classifier system
    classifier_string = zlib.decompress(classifier_string.decode('base64'))
    cl = mng.getMarSystem(classifier_string)
    # NOTE: the system is currently deactivated, but adding it to the net system will activate it
    # activating it now will trigger funny consequences when the net system starts updating controls

    # Set up up our other MarSystems
    rv = mng.create("RealvecSource", "rv")

    # set up the series
    net.addMarSystem(rv)
    net.addMarSystem(cl)

    # Set up the number of input samples to the system.
    # Don't know what this is for but we need it.
    net.updControl("mrs_natural/inSamples", fnat(1))

    # Set a "new" data source
    net.updControl("RealvecSource/rv/mrs_realvec/data", frvec(data))
    net.updControl("RealvecSource/rv/mrs_bool/done", fbool(False))

    # Loop over all the input, ticking the system, and classifying it
    guesses = []
    while not net.getControl("RealvecSource/rv/mrs_bool/done").to_bool():
        net.tick()
        output = net.getControl("mrs_realvec/processedData").to_realvec()
        distance = output[2]
        guesses.append(distance)

    return guesses

