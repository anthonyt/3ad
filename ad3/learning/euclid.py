from numpy import mean, array, dot, sqrt, subtract
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

# Initialize our main variables
distancematrix_ = "dm.txt"
classifier_ = "SVM"
wekafname_ = "input.arff"
mng = MarSystemManager()

def train():
    net = mng.create("Series", "net")

    # print a status message
    print "Training classifier using .arff file: ", wekafname_
    print "Classifier type : ", classifier_

    # Start setting up our MarSystems
    net.addMarSystem(mng.create("WekaSource", "wsrc"))
    net.addMarSystem(mng.create("Classifier", "cl"))
    net.addMarSystem(mng.create("Summary", "summary"))

    # Set up the appropriate classifier
    if classifier_ == "GS":
        net.updControl("Classifier/cl/mrs_string/enableChild", fstr("GaussianClassifier/gaussiancl"))
    elif classifier_ == "ZEROR":
        net.updControl("Classifier/cl/mrs_string/enableChild", fstr("ZeroRClassifier/zerorcl"))
    elif classifier_ == "SVM":
        net.updControl("Classifier/cl/mrs_string/enableChild", fstr("SVMClassifier/svmcl"))

    # Set the validation mode and input filename for our WekaSource
    net.updControl("WekaSource/wsrc/mrs_string/validationMode", fstr("kFold,NS,10"))
    net.updControl("WekaSource/wsrc/mrs_string/filename", fstr(wekafname_))

    # Set up our Summary system to mirror our WekaSource system
    net.updControl("Summary/summary/mrs_string/classNames", net.getControl("WekaSource/wsrc/mrs_string/classNames"))
    net.updControl("Summary/summary/mrs_natural/nClasses", net.getControl("WekaSource/wsrc/mrs_natural/nClasses"))

    # Set up the Classifier system
    net.updControl("Classifier/cl/mrs_natural/nClasses", net.getControl("WekaSource/wsrc/mrs_natural/nClasses"))
    net.linkControl("Classifier/cl/mrs_string/mode", "Summary/summary/mrs_string/mode")

    # Loop over all the input in the WekaSource, ticking the system, and updating the Classifier Mode
    while not net.getControl("WekaSource/wsrc/mrs_bool/done").to_bool():
        mode = net.getControl("WekaSource/wsrc/mrs_string/mode").to_string()
        net.tick()
        net.updControl("Classifier/cl/mrs_string/mode", fstr(mode))

    # Set the classifier to "predict" mode
    net.updControl("Classifier/cl/mrs_string/mode", fstr("predict"))

    # Tell our summary system that we're done
    net.updControl("Summary/summary/mrs_bool/done", fbool(True))

    # Tick the system one final time.
    net.tick()

    net.updControl("WekaSource/wsrc/mrs_string/filename", fstr("input2.arff"))
    # Loop over all the input in the WekaSource, ticking the system, and updating the Classifier Mode
    while not net.getControl("WekaSource/wsrc/mrs_bool/done").to_bool():
        mode = net.getControl("WekaSource/wsrc/mrs_string/mode").to_string()
        net.tick()
        net.updControl("Classifier/cl/mrs_string/mode", fstr(mode))

    net.tick()

def distance_matrix():
    print "\n\nDistance matrix calculation using ", wekafname_

    net = mng.create("Series", "net")
    accum = mng.create("Accumulator", "accum")

    wsrc = mng.create("WekaSource", "wsrc")
    accum.addMarSystem(wsrc)

    accum.updControl("WekaSource/wsrc/mrs_string/filename", fstr(wekafname_))

    nInstances = accum.getControl("WekaSource/wsrc/mrs_natural/nInstances").to_natural()
    accum.updControl("mrs_natural/nTimes", fnat(nInstances))

    # when we compiled marsyas, the SelfSimilarityMatrix was just called SimilarityMatrix
    #dmatrix = mng.create("SelfSimilarityMatrix", "dmatrix")
    dmatrix = mng.create("SimilarityMatrix", "dmatrix")
    if dmatrix is None:
        print "dmatrix is None! For some reason we couldn't instantiate a SelfSimilarityMatrix\n"
        exit(1);

    dmatrix.addMarSystem(mng.create("Metric", "dmetric"))
    dmatrix.updControl("Metric/dmetric/mrs_string/metric", fstr("euclideanDistance"))
    dmatrix.updControl("mrs_string/normalize", fstr("MinMax"))

    net.addMarSystem(accum)
    net.addMarSystem(dmatrix)

    net.tick()

    print "Marsyas-kea distance matrix for MIREX 2007 Audio Similarity Exchange "

    # "extract.txt" doesn't exist
    # and the Collection() class isn't available through SWIG
    #
    #l = Collection()
    #l.read("extract.txt")
    #
    #for i in range(0, l.size()):
    #    print i+1, "\t", l.entry(i)

    print "Q/R"
    dmx = net.getControl("mrs_realvec/processedData").to_realvec()

    out = ""
    for i in range(0, nInstances):
        out += "\t" + str(i+1)
    print out

    print array(dmx)
    print dmx

    for i in range(0, nInstances):
        out = str(i+1)
        for j in range(0, nInstances):
            out += "\t" + str(dmx[i*nInstances + j])
        print out

    print ""

