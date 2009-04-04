from numpy import mean, array, dot, sqrt, subtract, zeros
from twisted.internet import defer
from marsyas import *
from sys import exit
import zlib

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


    def calculate_tag_vector(self, callback, tag):
        outer_df = defer.Deferred()
        outer_df.addCallback(callback)

        def got_files(files):
            vector = mean([f.vector for f in files], axis=0).tolist()
            outer_df.callback(vector)

        self.model.get_audio_files(got_files, tag = tag)

        return outer_df


    def calculate_file_vector(self, callback, file):
        outer_df = defer.Deferred()
        outer_df.addCallback(callback)

        def got_outputs(plugin_outputs):
            vector = []
            for po in plugin_outputs:
                vector.extend(po.vector)
            outer_df.callback(vector)

        self.model.get_plugin_outputs(got_outputs, audio_file=file)

        return outer_df


    def does_tag_match(self, file, tag):
        distance = euclidean_distance(tag.vector, file.vector)
        print "DISTANCE:", distance, file, tag
        if distance <= self.tolerance:
            return True
        return False

# some more useful function names
fstr = MarControlPtr.from_string
fnat = MarControlPtr.from_natural
freal = MarControlPtr.from_real
fbool = MarControlPtr.from_bool
frvec = MarControlPtr.from_realvec

# Initialize our main variables
distancematrix_ = "dm.txt"
classifier_ = "SVM"
wekafname_ = "input.arff"
mng = MarSystemManager()

def to_realvec(matrix, cols):
    rows = len(matrix)
    vec = realvec(rows, cols)
    for i in range(0, rows):
        for j in range(0, cols):
            vec[j*rows+i] = matrix[i][j]
    return vec

def to_array(vec):
    rows = vec.getRows()
    cols = vec.getCols()
    arr = zeros((rows, cols))
    for i in range(0, rows):
        for j in range(0, cols):
            arr[i][j] = vec[j*rows + i]
    return (arr.tolist(), cols)

def test():
    # create an array of realvecs to classify
    data = [
        # format: [a, b, c, d, label]
        [1, 1, 2, 0],
        [1, 2, 1, 0],
        [2, 4, 6, 1],
        [2, 5, 9, 1],
        [2, 1, 1, 0],
        [2, 1, 2, 0],
        [2, 1, 9, 1]
    ]
    class_names = "first_class,second_class"
    num_classes = 2

    d1 = data
    d2 = data

    t_data_vec = to_realvec(d1, len(data[0]))
    p_data_vec = to_realvec(d2, len(data[0]))

    # RealvecSource uses columns instead of rows. god knows why
    t_data_vec.transpose()
    p_data_vec.transpose()

    classifier_string = train_gaussian(t_data_vec, num_classes)
    guesses_g = predict_gaussian(p_data_vec, num_classes, class_names, classifier_string)
    print "Size of classifier string:", len(classifier_string)

    classifier_string = train_svm(t_data_vec, num_classes)
    guesses_s = predict_svm(p_data_vec, num_classes, class_names, classifier_string)
    print "Size of classifier string:", len(classifier_string)

    for i in range(0, len(d2)):
        print "Actual:", d2[i][-1], "  SVM:", int(guesses_s[i][0]), "  Gaussian:", int(guesses_g[i][0]), "  Gaussian Distance:", guesses_g[i][2]


def train_gaussian(data, num_classes):
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
    net.updControl("Classifier/cl/mrs_natural/nClasses", fnat(num_classes))

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
    return zlib.compress(cl_str)


def predict_gaussian(data, num_classes, class_names, classifier_string):
    # create up our series system
    net = mng.create("Series", "net")

    # Un-serialize the Classifier system
    classifier_string = zlib.decompress(classifier_string)
    cl = mng.getMarSystem(classifier_string)
    # NOTE: the system is currently deactivated, but adding it to the net system will activate it
    # activating it now will trigger funny consequences when the net system starts updating controls

    # Set up up our other MarSystems
    rv = mng.create("RealvecSource", "rv")
    summary = mng.create("Summary", "summary")

    # set up the series
    net.addMarSystem(rv)
    net.addMarSystem(cl)
    net.addMarSystem(summary)

    # Set up the number of input samples to the system.
    # Don't know what this is for but we need it.
    net.updControl("mrs_natural/inSamples", fnat(1))

    # Set up our Summary system to mirror our data
    net.updControl("Summary/summary/mrs_string/classNames", fstr(class_names))
    net.updControl("Summary/summary/mrs_natural/nClasses", fnat(num_classes))

    # Set a "new" data source
    net.updControl("RealvecSource/rv/mrs_realvec/data", frvec(data))
    net.updControl("RealvecSource/rv/mrs_bool/done", fbool(False))

    # Loop over all the input, ticking the system, and classifying it
    net.updControl("Summary/summary/mrs_string/mode", fstr("predict"))
    guesses = []
    while not net.getControl("RealvecSource/rv/mrs_bool/done").to_bool():
        net.tick()
        o = net.getControl("Classifier/cl/mrs_realvec/processedData").to_realvec()
        guesses.append(array(o))

    # Tell our summary system that we're done
    net.updControl("Summary/summary/mrs_bool/done", fbool(True))

    # Tick the system one final time. This will make the Summary system print its report.
    net.tick()

    return guesses


def train_svm(data, num_classes):
    net = mng.create("Series", "net")

    # Start setting up our MarSystems
    rv = mng.create("RealvecSource", "rv")
    cl = mng.create("Classifier", "cl")
    net.addMarSystem(rv)
    net.addMarSystem(cl)

    # Set up the appropriate classifier
    net.updControl('Classifier/cl/mrs_string/enableChild', fstr('SVMClassifier/svmcl'))
#    net.updControl('Classifier/cl/SVMClassifier/svmcl/mrs_string/svm', fstr('ONE_CLASS'))

    # Set up the number of input samples to the system.
    # Don't know what this is for but we need it.
    net.updControl("mrs_natural/inSamples", fnat(1))

    net.updControl("RealvecSource/rv/mrs_realvec/data", frvec(data))

    # Set up the Classifier system
    net.updControl("Classifier/cl/mrs_natural/nClasses", fnat(num_classes))

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
    return zlib.compress(cl_str)


def predict_svm(data, num_classes, class_names, classifier_string):
    # create up our series system
    net = mng.create("Series", "net")

    # Un-serialize the Classifier system
    classifier_string = zlib.decompress(classifier_string)
    cl = mng.getMarSystem(classifier_string)
    # NOTE: the system is currently deactivated, but adding it to the net system will activate it
    # activating it now will trigger funny consequences when the net system starts updating controls

    # Set up up our other MarSystems
    rv = mng.create("RealvecSource", "rv")
    summary = mng.create("Summary", "summary")

    # set up the series
    net.addMarSystem(rv)
    net.addMarSystem(cl)
    net.addMarSystem(summary)

    # Set up the number of input samples to the system.
    # Don't know what this is for but we need it.
    net.updControl("mrs_natural/inSamples", fnat(1))

    # Set up our Summary system to mirror our data
    net.updControl("Summary/summary/mrs_string/classNames", fstr(class_names))
    net.updControl("Summary/summary/mrs_natural/nClasses", fnat(num_classes))

    # Set a "new" data source
    net.updControl("RealvecSource/rv/mrs_realvec/data", frvec(data))
    net.updControl("RealvecSource/rv/mrs_bool/done", fbool(False))

    # Loop over all the input, ticking the system, and classifying it
    net.updControl("Summary/summary/mrs_string/mode", fstr("predict"))
    guesses = []
    while not net.getControl("RealvecSource/rv/mrs_bool/done").to_bool():
        net.tick()
        o = net.getControl("Classifier/cl/mrs_realvec/processedData").to_realvec()
        guesses.append(array(o))

    # Tell our summary system that we're done
    net.updControl("Summary/summary/mrs_bool/done", fbool(True))

    # Tick the system one final time. This will make the Summary system print its report.
    net.tick()

    return guesses
