from numpy import mean, array, dot, sqrt, subtract, zeros
from twisted.internet import defer
from marsyas import *
from sys import exit

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

def to_realvec(matrix):
    rows = len(matrix)
    cols = len(matrix[0])
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
    return arr

def train():
    net = mng.create("Series", "net")

    # Start setting up our MarSystems
    net.addMarSystem(mng.create("RealvecSource", "rv"))
    net.addMarSystem(mng.create("Classifier", "cl"))
    net.addMarSystem(mng.create("Summary", "summary"))

    # Set up the appropriate classifier
    if classifier_ == "GS":
        net.updControl("Classifier/cl/mrs_string/enableChild", fstr("GaussianClassifier/gaussiancl"))
    elif classifier_ == "ZEROR":
        net.updControl("Classifier/cl/mrs_string/enableChild", fstr("ZeroRClassifier/zerorcl"))
    elif classifier_ == "SVM":
        net.updControl("Classifier/cl/mrs_string/enableChild", fstr("SVMClassifier/svmcl"))

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
    data = to_realvec(data)
    class_names = "first_class,second_class"
    num_classes = 2
    """
    To use the data from the kea tests:
    data = get_input()
    data = to_realvec(data)
    class_names = "blues,classical,country,disco,hiphop,jazz,metal,pop,reggae,rock"
    num_classes = 10
    """
    # RealvecSource uses columns instead of rows. god knows why
    data.transpose()

    # Set up the number of input samples to the system.
    # Don't know what this is for but we need it.
    net.updControl("mrs_natural/inSamples", fnat(1))

    # Set up our Summary system to mirror our data
    net.updControl("RealvecSource/rv/mrs_realvec/data", frvec(data))
    net.updControl("Summary/summary/mrs_string/classNames", fstr(class_names))
    net.updControl("Summary/summary/mrs_natural/nClasses", fnat(num_classes))

    # Set up the Classifier system
    net.updControl("Classifier/cl/mrs_natural/nClasses", fnat(num_classes))
    net.linkControl("Classifier/cl/mrs_string/mode", "Summary/summary/mrs_string/mode")

    # Loop over all the input, ticking the system, and updating the Classifier Mode
    net.updControl("Classifier/cl/mrs_string/mode", fstr("train"))
    while not net.getControl("RealvecSource/rv/mrs_bool/done").to_bool():
        net.tick()

    # Set a "new" data source
    net.updControl("RealvecSource/rv/mrs_realvec/data", frvec(data))
    net.updControl("RealvecSource/rv/mrs_bool/done", fbool(False))

    # Loop over all the input, ticking the system, and classifying it
    net.updControl("Classifier/cl/mrs_string/mode", fstr("predict"))
    while not net.getControl("RealvecSource/rv/mrs_bool/done").to_bool():
        net.tick()

    # Tell our summary system that we're done
    net.updControl("Summary/summary/mrs_bool/done", fbool(True))

    # Tick the system one final time. This will make the Summary system print its report.
    net.tick()



