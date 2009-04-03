from numpy import mean, array, dot, sqrt, subtract, zeros
from twisted.internet import defer
from marsyas import *
from sys import exit

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
    data = to_realvec(data, 4)
    class_names = "first_class,second_class"
    num_classes = 2
    # RealvecSource uses columns instead of rows. god knows why
    data.transpose()

    classifier_string = train(data, num_classes, class_names)
    predict(data, num_classes, class_names, classifier_string)


def train(data, num_classes, class_names):
    net = mng.create("Series", "net")

    # Start setting up our MarSystems
    rv = mng.create("RealvecSource", "rv")
    cl = mng.create("Classifier", "cl")
    net.addMarSystem(rv)
    net.addMarSystem(cl)

    # Set up the appropriate classifier
    classifier_children = [('/Series/net/Classifier/cl/mrs_string/enableChild', 'SVMClassifier/svmcl')]
    cl.updControl(classifier_children[0][0], fstr(classifier_children[0][1]))

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

    return cl.toString()


def predict(data, num_classes, class_names, classifier_string):
    # create up our series system
    net = mng.create("Series", "net")

    # Start setting up our MarSystems
    rv = mng.create("RealvecSource", "rv")
    cl = mng.getMarSystem(classifier_string)
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
    net.linkControl("Classifier/cl/mrs_string/mode", "Summary/summary/mrs_string/mode")

    # Set a "new" data source
    net.updControl("RealvecSource/rv/mrs_realvec/data", frvec(data))
    net.updControl("RealvecSource/rv/mrs_bool/done", fbool(False))

    # Loop over all the input, ticking the system, and classifying it
    net.updControl("Classifier/cl/mrs_string/mode", fstr("predict"))
    while not net.getControl("RealvecSource/rv/mrs_bool/done").to_bool():
        net.tick()
        o = net.getControl("Classifier/cl/mrs_realvec/processedData").to_realvec()
        print array(o)

    # Tell our summary system that we're done
    net.updControl("Summary/summary/mrs_bool/done", fbool(True))

    # Tick the system one final time. This will make the Summary system print its report.
    net.tick()


