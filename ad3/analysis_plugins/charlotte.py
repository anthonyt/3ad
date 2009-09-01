from marsyas import *
from numpy import array

def createVector(filename):
    mng = MarSystemManager()
    fnet = mng.create("Series", "fnet")

    hz_sr = 11250   # samples per second
    s_duration = 30 # seconds
    win_size = 1024 # samples per window
    hop_size = win_size / 2
    num_frames = 66 # makes a 3 second window

    #------------------ Feature Network ------------------------------

    # Decode the file, downmix to mono, and downsample
    fnet.addMarSystem(mng.create("SoundFileSource", "src"))
    fnet.addMarSystem(mng.create("DownSampler", "ds"))
    fnet.addMarSystem(mng.create("Stereo2Mono", "s2m"))

    # Create the feature extractor

    fnet.addMarSystem(mng.create("TimbreFeatures", "tf"))
    fnet.updControl("TimbreFeatures/tf/mrs_string/enableTDChild", MarControlPtr.from_string("ZeroCrossings/zcrs"))
    fnet.updControl("TimbreFeatures/tf/mrs_string/enableSPChild", MarControlPtr.from_string("MFCC/mfcc"))
    fnet.updControl("TimbreFeatures/tf/mrs_string/enableSPChild", MarControlPtr.from_string("Centroid/cntrd"))
    fnet.updControl("TimbreFeatures/tf/mrs_string/enableSPChild", MarControlPtr.from_string("Flux/flux"))
    fnet.updControl("TimbreFeatures/tf/mrs_string/enableSPChild", MarControlPtr.from_string("Rolloff/rlf"))

    # Add the texture statistics
    fnet.addMarSystem(mng.create("TextureStats", "tStats"))

    #------------------- Set Parameters ------------------------------

    # Set the texture memory size to a 3-second window (66 analysis frames)
    fnet.updControl("TextureStats/tStats/mrs_natural/memSize", MarControlPtr.from_natural(num_frames))

    # Set the file name
    fnet.updControl("SoundFileSource/src/mrs_string/filename", MarControlPtr.from_string(filename))

    # Set the sample rate to 11250 Hz
    factor = int(round(fnet.getControl("SoundFileSource/src/mrs_real/osrate").to_real()/hz_sr))
    fnet.updControl("DownSampler/ds/mrs_natural/factor", MarControlPtr.from_natural(factor))

    # Set the window to 1024 samples at 11250 Hz
    # Should be able to set with simply TimbreFeatures/tf/mrs_natural/winSize,
    # but that doesn't seem to work
    fnet.updControl("TimbreFeatures/tf/Series/timeDomain/ShiftInput/si/mrs_natural/winSize", MarControlPtr.from_natural(win_size))
    fnet.updControl("TimbreFeatures/tf/Series/spectralShape/ShiftInput/si/mrs_natural/winSize", MarControlPtr.from_natural(win_size))
    fnet.updControl("TimbreFeatures/tf/Series/lpcFeatures/ShiftInput/si/mrs_natural/winSize", MarControlPtr.from_natural(win_size))

    # Find the length of the song
    slength = fnet.getControl("SoundFileSource/src/mrs_natural/size").to_natural()

    if slength is 0:
        raise Exception('InvalidLengthError', "File \"%s\" could not be read." % filename)

    # Find the number of samples resulting in a whole number of analysis windows by truncating
    numsamps = int(s_duration * hz_sr * factor) / hop_size * hop_size

    # Shift the start over so that the duration is in the middle
    start = int((slength - numsamps)/2)

    fnet.updControl("SoundFileSource/src/mrs_natural/pos", MarControlPtr.from_natural(start))
    fnet.updControl("SoundFileSource/src/mrs_real/duration", MarControlPtr.from_real(numsamps))

    # ----------------- Accumulator ---------------------------------

    # Accumulate over the entire song
    acc = mng.create("Accumulator", "acc")

    # nTimes is measured in number of analysis windows
    nTimes = int((s_duration * hz_sr) / hop_size)
    acc.updControl("mrs_natural/nTimes", MarControlPtr.from_natural(nTimes))

    #------------------ Song Statistics -----------------------------
    # Fanout and calculate mean and standard deviation
    sstats = mng.create("Fanout", "sstats")
    sstats.addMarSystem(mng.create("Mean", "smn"))
    sstats.addMarSystem(mng.create("StandardDeviation", "sstd"))

    # ----------------- Top Level Network Wrapper -------------------

    # (src->downmix->downsample->features->texture stats)
    # -->accumulator->song stats->output
    tnet = mng.create("Series", "tnet")
    acc.addMarSystem(fnet)
    tnet.addMarSystem(acc)
    tnet.addMarSystem(sstats)

    # set the hop size to 512 (needs to be set for the top-level network)
    tnet.updControl("mrs_natural/inSamples", MarControlPtr.from_natural(factor*hop_size))

    # Should only need to tick once
    tnet.tick()

    result = tnet.getControl("mrs_realvec/processedData").to_realvec()
    result.normMaxMin()

    # convert from useless marsyas vector to numpy array to normal python list
    result = array(result) * 100;

    return [float(x) for x in result]


    """
    feature extractor (get a vector) -> annotator (append the number for the class of the output, like, the tag id) --> classifier (train mode) (output actual tag_id, guessed tag_id, as a tuple)
    """
