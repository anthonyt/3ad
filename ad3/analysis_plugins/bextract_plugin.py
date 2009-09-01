# bextract implemented using the swig python Marsyas bindings
# Modified (August, 2009) by Anthony Theocharis,
# from code by George Tzanetakis (January, 16, 2007)
from marsyas import *
from numpy import mean, array, dot, sqrt, subtract, zeros, copy

fstr = MarControlPtr.from_string
fnat = MarControlPtr.from_natural
freal = MarControlPtr.from_real
fbool = MarControlPtr.from_bool
frvec = MarControlPtr.from_realvec

# FIXME: Rolloff, Flux, Centroid, and Zero crossing all seem to only contribute
#        2 useful numbers. However they all contribute a bunch of zeroes.
chroma_ = False or True
mfcc_ = False or True
sfm_ = False or True
scf_ = False or True
rlf_ = False or True
flx_ = False or True
lsp_ = False or True
lpcc_ = False or True
ctd_ = False or True
zcrs_ = False or True
# These just duplicate above features.
spectralFeatures_ = False
timbralFeatures_ = False
hopSize = 512
winSize = 512
start = 0
length = -1.0
downSample = 1

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

def selectFeatureSet(featExtractor):
    if chroma_:
        featExtractor.updControl("mrs_string/enableSPChild", fstr("Spectrum2Chroma/chroma"))
    if mfcc_:
        featExtractor.updControl("mrs_string/enableSPChild", fstr("MFCC/mfcc"))
    if sfm_:
        featExtractor.updControl("mrs_string/enableSPChild", fstr("SFM/sfm"))
    if scf_:
        featExtractor.updControl("mrs_string/enableSPChild", fstr("SCF/scf"))
    if rlf_:
        featExtractor.updControl("mrs_string/enableSPChild", fstr("Rolloff/rlf"))
    if flx_:
        featExtractor.updControl("mrs_string/enableSPChild", fstr("Flux/flux"))
    if lsp_:
        featExtractor.updControl("mrs_string/enableLPCChild", fstr("Series/lspbranch"))
    if lpcc_:
        featExtractor.updControl("mrs_string/enableLPCChild", fstr("Series/lpccbranch"))
    if ctd_:
        featExtractor.updControl("mrs_string/enableSPChild", fstr("Centroid/cntrd"))
    if zcrs_:
        featExtractor.updControl("mrs_string/enableTDChild", fstr("ZeroCrossings/zcrs"))
    if spectralFeatures_:
        featExtractor.updControl("mrs_string/enableSPChild", fstr("Centroid/cntrd"))
        featExtractor.updControl("mrs_string/enableSPChild", fstr("Flux/flux"))
        featExtractor.updControl("mrs_string/enableSPChild", fstr("Rolloff/rlf"))
    if timbralFeatures_:
        featExtractor.updControl("mrs_string/enableTDChild", fstr("ZeroCrossings/zcrs"))
        featExtractor.updControl("mrs_string/enableSPChild", fstr("MFCC/mfcc"))
        featExtractor.updControl("mrs_string/enableSPChild", fstr("Centroid/cntrd"))
        featExtractor.updControl("mrs_string/enableSPChild", fstr("Flux/flux"))
        featExtractor.updControl("mrs_string/enableSPChild", fstr("Rolloff/rlf"))

def bextract_train_refactored(filename="bextract_single.mf", playlist=True, wekafname="", mem_size=1, stereo_=False, acc_size=400):
    # bnet(                                                 <- series
    #    acc( fnet( src, s2m, featExtractor, tStats ) ),    <- accumulator ( series )
    #    song_statistics( mn & std ),                       <- fanout
    #    annotator,                                         <- annotator
    #    wSink                                              <- wekaSink
    # )

    mng = MarSystemManager()

    # Build the overall feature calculation network
    fnet = mng.create("Series", "featureNetwork")

    # Overall extraction and classification network
    bnet = mng.create("Series", "bextractNetwork")

    # Add a sound file source (which can also read collections)
    src = mng.create("SoundFileSource", "src")

    # Use accumulator if computing single vector per file
    acc = mng.create("Accumulator", "acc")

    # labeling, weka output, classifier and confidence for real-time output
    annotator = mng.create("Annotator", "annotator")

    fnet.addMarSystem(src)

    # Select whether stereo or mono feature extraction is to be used
    if stereo_ == True:
        stereoFeatures = mng.create("StereoFeatures", "stereoFeatures")
        selectFeatureSet(stereoFeatures)
        fnet.addMarSystem(stereoFeatures)
    else:
        fnet.addMarSystem(mng.create("Stereo2Mono", "s2m"))
        featExtractor = mng.create("TimbreFeatures", "featExtractor")
        selectFeatureSet(featExtractor)
        fnet.addMarSystem(featExtractor)

    # texture statistics
    fnet.addMarSystem(mng.create("TextureStats", "tStats"))
    fnet.updControl("TextureStats/tStats/mrs_natural/memSize", fnat(mem_size))
    fnet.updControl("TextureStats/tStats/mrs_bool/reset", fbool(True))

    # Set up the accumulator
    acc.updControl("mrs_natural/nTimes", fnat(acc_size))
    acc.addMarSystem(fnet)

    # Set up some stats tracking
    song_statistics = mng.create("Fanout", "song_statistics")
    song_statistics.addMarSystem(mng.create("Mean", "mn"))
    song_statistics.addMarSystem(mng.create("StandardDeviation", "std"))

    # Add the accumulator, stats tracking, and annotator to the bextractNetwork series
    bnet.addMarSystem(acc)
    bnet.addMarSystem(song_statistics)
    bnet.addMarSystem(annotator)

    bnet.linkControl(
        "Accumulator/acc/Series/featureNetwork/SoundFileSource/src/mrs_string/filename",
        "mrs_string/filename")
    bnet.linkControl(
        "mrs_bool/notEmpty",
        "Accumulator/acc/Series/featureNetwork/SoundFileSource/src/mrs_bool/notEmpty")
    bnet.linkControl(
        "mrs_natural/pos",
        "Accumulator/acc/Series/featureNetwork/SoundFileSource/src/mrs_natural/pos")
    bnet.linkControl(
        "mrs_real/duration",
        "Accumulator/acc/Series/featureNetwork/SoundFileSource/src/mrs_real/duration")
    bnet.linkControl(
        "mrs_string/currentlyPlaying",
        "Accumulator/acc/Series/featureNetwork/SoundFileSource/src/mrs_string/currentlyPlaying")
    bnet.linkControl(
        "mrs_natural/currentLabel",
        "Accumulator/acc/Series/featureNetwork/SoundFileSource/src/mrs_natural/currentLabel")
    bnet.linkControl(
        "mrs_natural/nLabels",
        "Accumulator/acc/Series/featureNetwork/SoundFileSource/src/mrs_natural/nLabels")
    bnet.linkControl(
        "mrs_string/labelNames",
        "Accumulator/acc/Series/featureNetwork/SoundFileSource/src/mrs_string/labelNames")
    bnet.linkControl(
        "Accumulator/acc/Series/featureNetwork/SoundFileSource/src/mrs_natural/advance",
        "mrs_natural/advance")
    bnet.linkControl(
        "Annotator/annotator/mrs_natural/label",
        "mrs_natural/currentLabel")

    # links with WekaSink
    if wekafname != "":
        wsink = mng.create("WekaSink", "wsink")
        bnet.addMarSystem(wsink)
        bnet.linkControl(
            "WekaSink/wsink/mrs_string/currentlyPlaying",
            "mrs_string/currentlyPlaying")
        bnet.linkControl(
            "WekaSink/wsink/mrs_string/labelNames",
            "mrs_string/labelNames")
        bnet.linkControl(
            "WekaSink/wsink/mrs_natural/nLabels",
            "mrs_natural/nLabels")

    # src has to be configured with hopSize frame length in case a ShiftInput
    # is used in the feature extraction network
    bnet.updControl("mrs_natural/inSamples", fnat(hopSize))
    if stereo_:
        fnet.updControl(
            "StereoFeatures/stereoFeatures/mrs_natural/winSize",
            fnat(winSize))
    else:
        fnet.updControl(
            "TimbreFeatures/featExtractor/mrs_natural/winSize",
            fnat(winSize))

    if start > 0:
        offset = start * src.getControl("mrs_real/israte").to_real()
    else:
        offset = 0

    bnet.updControl("mrs_natural/pos", fnat(offset))
    bnet.updControl("mrs_real/duration", freal(length))

    # load the collection which is automatically created by bextract
    bnet.updControl("mrs_string/filename", fstr(filename))

    # setup WekaSink - has to be done after all updates so that changes are correctly
    # written to file
    if wekafname != "":
        bnet.updControl("WekaSink/wsink/mrs_natural/downsample", fnat(downSample))
        bnet.updControl("WekaSink/wsink/mrs_string/filename", fstr(wekafname))

    # main processing loop for training
    ctrl_notEmpty = bnet.getControl("mrs_bool/notEmpty")
    ctrl_currentlyPlaying = bnet.getControl("mrs_string/currentlyPlaying")

    previouslyPlaying = ""
    currentlyPlaying = ""
    n = 0
    advance = 1
    processedFiles = []
    processedFeatures = {}
    fvec = []
    label = 0

    if playlist:
        # Use this loop when reading from a playlist (ie *.mf format)
        while ctrl_notEmpty.to_bool():
            currentlyPlaying = ctrl_currentlyPlaying.to_string()
            label = bnet.getControl("mrs_natural/currentLabel").to_natural()

            if currentlyPlaying in processedFiles:
                # This only gets reached when the method is called with an audio file as the filename, instaed of a playlist
                advance += 1
                bnet.updControl("mrs_natural/advance", fnat(advance))

                fvec = processedFeatures[currentlyPlaying]
                fvec[fvec.getSize()-1] = label

                if wekafname != "":
                    bnet.updControl("WekaSink/wsink/mrs_string/injectComment", fstr("% filename " + currentlyPlaying))
                    bnet.updControl("WekaSink/wsink/mrs_realvec/injectVector", frvec(fvec))
                    bnet.updControl("WekaSink/wsink/mrs_bool/inject", fbool(True))
            else:
                bnet.updControl("Accumulator/acc/Series/featureNetwork/TextureStats/tStats/mrs_bool/reset", fbool(True))
                bnet.tick()

                # FIXME: For some strange reason, this control requires the wekasink to exist. ARGH
                # fvec = bnet.getControl("Annotator/annotator/mrs_realvec/processedData").to_realvec()
                fvec = bnet.getControl("Fanout/song_statistics/mrs_realvec/processedData").to_realvec()

                bnet.updControl("mrs_natural/advance", fnat(advance))
                processedFiles.append(currentlyPlaying)
                processedFeatures[currentlyPlaying] = fvec
                advance = 1
                bnet.updControl("mrs_natural/advance", fnat(1))
            n += 1
    else:
        # Use this loop when only using one input file.
        bnet.updControl("Accumulator/acc/Series/featureNetwork/TextureStats/tStats/mrs_bool/reset", fbool(True))
        currentlyPlaying = ctrl_currentlyPlaying.to_string()

        while ctrl_notEmpty.to_bool():
            bnet.tick()

        # FIXME: For some strange reason, this control requires the wekasink to exist. ARGH
        # fvec = bnet.getControl("Annotator/annotator/mrs_realvec/processedData").to_realvec()
        fvec = bnet.getControl("Fanout/song_statistics/mrs_realvec/processedData").to_realvec()
        if wekafname != "":
            bnet.updControl("WekaSink/wsink/mrs_string/injectComment", fstr("% filename " + currentlyPlaying))
            bnet.updControl("WekaSink/wsink/mrs_realvec/injectVector", frvec(fvec))
            bnet.updControl("WekaSink/wsink/mrs_bool/inject", fbool(True))

        processedFiles.append(currentlyPlaying)
        processedFeatures[currentlyPlaying] = fvec

    return processedFeatures

def createVector(filename):
    vec = bextract_train_refactored(filename=filename, playlist=False)
    for key in vec: # there should be only one
        vec[key].transpose()
        vec[key] = realvec_to_list(vec[key])[0][0]
        result = vec[key]
        return [float(x) for x in array(result)]

