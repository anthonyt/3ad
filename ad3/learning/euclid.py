from numpy import mean, array, dot, sqrt, subtract, zeros, copy
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

    training_class = 1
    d1 = copy([d for d in data if d[-1] == training_class])
    d2 = copy(data)
    for d in d1:
        d[-1] = 0
    for d in d2:
        d[-1] = 0

    t_data_vec = to_realvec(d1, len(data[0]))
    p_data_vec = to_realvec(d2, len(data[0]))

    # RealvecSource uses columns instead of rows. god knows why
    t_data_vec.transpose()
    p_data_vec.transpose()

    # Get the gaussian guesses. Give a tolerance of 100
    classifier_string = train_gaussian(t_data_vec)
    guesses_g = predict_gaussian(p_data_vec, classifier_string)
    guesses_g = [g[2] < 100 for g in guesses_g]
    print "Size of classifier string:", len(classifier_string)

    # Get the SVM guesses. 1 == True, -1 == False
    classifier_string = train_svm(t_data_vec)
    guesses_s = predict_svm(p_data_vec, classifier_string)
    guesses_s = [s[0]==1 for s in guesses_s]
    print "Size of classifier string:", len(classifier_string)

    # Get the euclidean guesses. Give a tolerance of 5.
    means = mean(d1, axis=0)
    guesses_e = [euclidean_distance(d, means)<5 for d in d2]

    answers = [[
                data[i][-1]==training_class,
                guesses_s[i],
                guesses_g[i],
                guesses_e[i]
               ] for i in range(0, len(d2)) ]

    s1 = [b for b in answers if b[0] is True]
    total_p = len(s1)
    svm_tp = float(len([a for a in s1 if a[1] == True]))
    gau_tp = float(len([a for a in s1 if a[2] == True]))
    euc_tp = float(len([a for a in s1 if a[3] == True]))

    s2 = [b for b in answers if b[0] is False]
    total_n = len(s2)
    svm_tn = float(len([a for a in s2 if a[1] == False]))
    gau_tn = float(len([a for a in s2 if a[2] == False]))
    euc_tn = float(len([a for a in s2 if a[3] == False]))

    svm_recall = svm_tp/total_p
    gau_recall = gau_tp/total_p
    euc_recall = euc_tp/total_p
    svm_spec = svm_tn/total_n
    gau_spec = gau_tn/total_n
    euc_spec = euc_tn/total_n

    """
    for i in range(0, len(d2)):
        print "Actual:", answers[i][0], \
            "  SVM:", answers[i][1], \
            "  Gaussian:", answers[i][2], \
            "  Euclidean:", answers[i][3]
    """

    # Print a report
    print "SVM Recall:      ", svm_recall, "  SVM Specificity:      ", svm_spec
    print "Gaussian Recall: ", gau_recall, "  Gaussian Specificity: ", gau_spec
    print "Euclidean Recall:", euc_recall, "  Euclidean Specificity:", euc_spec



def train_gaussian(data):
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
    return zlib.compress(cl_str)


def predict_gaussian(data, classifier_string):
    # create up our series system
    net = mng.create("Series", "net")

    # Un-serialize the Classifier system
    classifier_string = zlib.decompress(classifier_string)
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
        o = net.getControl("mrs_realvec/processedData").to_realvec()
        guesses.append(array(o))

    return guesses


def train_svm(data):
    net = mng.create("Series", "net")

    # Start setting up our MarSystems
    rv = mng.create("RealvecSource", "rv")
    cl = mng.create("Classifier", "cl")
    net.addMarSystem(rv)
    net.addMarSystem(cl)

    # Set up the appropriate classifier
    net.updControl('Classifier/cl/mrs_string/enableChild', fstr('SVMClassifier/svmcl'))
    net.updControl('Classifier/cl/SVMClassifier/svmcl/mrs_string/svm', fstr('ONE_CLASS'))
    # Tweak some values. Got knows what these actually do. SVM math uses so many variables...
    net.updControl("Classifier/cl/SVMClassifier/svmcl/mrs_real/nu", freal(0.01));
    net.updControl("Classifier/cl/SVMClassifier/svmcl/mrs_natural/gamma", fnat(4));
    net.updControl("Classifier/cl/SVMClassifier/svmcl/mrs_string/kernel", fstr("RBF"));


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
    return zlib.compress(cl_str)


def predict_svm(data, classifier_string):
    # create up our series system
    net = mng.create("Series", "net")

    # Un-serialize the Classifier system
    classifier_string = zlib.decompress(classifier_string)
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
        o = net.getControl("mrs_realvec/processedData").to_realvec()
        guesses.append(array(o))

    return guesses
