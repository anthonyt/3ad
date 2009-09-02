from numpy import mean, array, dot, sqrt, subtract, zeros, copy
from twisted.internet import defer
from marsyas import *
import zlib
from .. import logs
logger = logs.logger

class Gaussian(object):
    def __init__(self, data_model, tolerable_distance = 100):
        self.model = data_model
        self.tolerance = tolerable_distance

    def calculate_file_and_tag_vectors(self, user_name=None):
        scoped_tags = []
        scoped_files = []
        scoped_files_by_tag = {}
        po_cmp = lambda a, b: cmp(a.plugin_key, b.plugin_key)
        tag_cmp = lambda a, b: cmp(a.key, b.key)

        def get_files(val):
            df = self.model.get_audio_files(user_name=user_name)
            return df

        def get_tags(val):
            df = self.model.get_tags()
            return df

        def got_files(files):
            for f in files:
                scoped_files.append(f)
            return None

        def got_tags(tags):
            for t in tags:
                scoped_tags.append(t)

            scoped_tags.sort(tag_cmp)
            return None

        def calculate_first_file_vectors(val):
            dfs = []

            def got_outputs(plugin_outputs, file):
                vec1 = []
                vec2 = file.vector and file.vector[1] or None

                # sort the plugin_outputs by plugin key.
                for po in sorted(plugin_outputs, po_cmp):
                    logger.debug("Appending vector of length %r to %r", len(po.vector), file)
                    vec1.extend(po.vector)

                file.vector = [vec1, vec2]

            for file in scoped_files:
                df = self.model.get_plugin_outputs(audio_file=file)
                df.addCallback(got_outputs, file)
                dfs.append(df)

            return defer.DeferredList(dfs)

        def calculate_first_tag_vectors(val):
            dfs = []

            def got_files(files, tag):
                scoped_files_by_tag[tag.key] = [f.key for f in files]
                vectors = [f.vector[0] for f in files]
                try:
                    vec1 = train(vectors)
                except Exception, e:
                    for i in range(0, len(vectors)):
                        logger.debug('Vector %d(%d): %r', i, len(vectors[i]), vectors[i])
                    raise e
                vec2 = tag.vector and tag.vector[1] or None
                tag.vector = [vec1, vec2]

            for tag in scoped_tags:
                df = self.model.get_audio_files(tag = tag, user_name=user_name)
                df.addCallback(got_files, tag)
                dfs.append(df)

            return defer.DeferredList(dfs)

        def calculate_second_file_vectors(val):
            for file in scoped_files:
                vec1 = file.vector[0]
                vec2 = []
                for tag in scoped_tags:
                    prediction = predict([vec1], tag.vector[0])
                    vec2.append(prediction[0])

                file.vector = [vec1, vec2]

            return None

        def calculate_second_tag_vectors(val):
            for tag in scoped_tags:
                files = [
                    f for f in scoped_files
                    if f.key in scoped_files_by_tag[tag.key]
                ]
                vectors = [f.vector[1] for f in files]
                vec1 = tag.vector[0]
                logger.debug("Training second with %r", vectors)
                vec2 = train(vectors)
                tag.vector = [vec1, vec2]

            return None

        def save_files_and_tags(val):
            dfs = []

            for file in scoped_files:
                df = self.model.save(file)
                dfs.append(df)

            for tag in scoped_tags:
                df = self.model.save(tag)
                dfs.append(df)

            return defer.DeferredList(dfs)

        df = defer.Deferred()
        df.addCallback(get_files)
        df.addCallback(got_files)
        df.addCallback(get_tags)
        df.addCallback(got_tags)
        df.addCallback(calculate_first_file_vectors)
        df.addCallback(calculate_first_tag_vectors)
        df.addCallback(calculate_second_file_vectors)
        df.addCallback(calculate_second_tag_vectors)
        df.addCallback(save_files_and_tags)
        df.callback(None)
        return df


    def calculate_tag_vector(self, tag):
        def got_files(files):
            vectors = [f.vector[0] for f in files]
            vec1 = train(vectors)
            vec2 = tag.vector and tag.vector[1] or None

            return [vec1, vec2]

        df = self.model.get_audio_files(tag = tag)
        df.addCallback(got_files)
        return df


    def calculate_file_vector(self, file):
        def got_outputs(plugin_outputs):
            c = lambda a, b: cmp(a.plugin_key, b.plugin_key)
            vec1 = []
            vec2 = file.vector and file.vector[1] or None

            # sort the plugin_outputs by plugin key.
            for po in sorted(plugin_outputs, c):
                vec1.extend(po.vector)

            return [vec1, vec2]

        df = self.model.get_plugin_outputs(audio_file=file)
        df.addCallback(got_outputs)
        return df


    def calculate_second_tag_vector(self, tag):
        def got_files(files):
            vectors = [f.vector[1] for f in files]
            vec1 = tag.vector and tag.vector[0] or None
            vec2 = train(vectors)

            return [vec1, vec2]

        df = self.model.get_audio_files(tag = tag)
        df.addCallback(got_files)
        return df


    def calculate_second_file_vector(self, file):
        def got_tags(tags):
            logger.debug("guess_tags")
            # Sort the tags! Important!
            c = lambda a, b: cmp(a.key, b.key)

            vec1 = file.vector[0]
            vec2 = [
                predict([file.vector[0]], tag.vector[0])[0]
                for tag in sorted(tags, c)
            ]

            return [vec1, vec2]

        df = self.model.get_tags()
        df.addCallback(got_tags)
        return df


    def does_tag_match(self, file, tag):
        data = [file.vector[1]]
        distances = predict(data, tag.vector[1])
        logger.info("DISTANCE: %r %r %r", distances[0], tag, file)
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
    logger.debug("len(data) = %d; len(data[0]) = %d, type(data) = %r; type(data[0]) = %r", len(data), len(data[0]), type(data), type(data[0]))
    data = prepare_data(data)
    net = mng.create("Series", "net")

    # Start setting up our MarSystems
    rv = mng.create("RealvecSource", "rv")
    cl = mng.create("GaussianClassifier", "cl")
    net.addMarSystem(rv)
    net.addMarSystem(cl)

    # Set up the number of input samples to the system.
    # Don't know what this is for but we need it.
    net.updControl("mrs_natural/inSamples", fnat(1))

    net.updControl("RealvecSource/rv/mrs_realvec/data", frvec(data))

    # Set up the Classifier system
    net.updControl("GaussianClassifier/cl/mrs_natural/nClasses", fnat(1))

    # Loop over all the input, ticking the system, and updating the Classifier Mode
    net.updControl("GaussianClassifier/cl/mrs_string/mode", fstr("train"))
    while not net.getControl("RealvecSource/rv/mrs_bool/done").to_bool():
        net.tick()

    # Take the system out of training mode, and tick it once to save its state
    net.updControl("GaussianClassifier/cl/mrs_string/mode", fstr("predict"))
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

