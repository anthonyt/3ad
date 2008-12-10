# bextract implemented using the swig python Marsyas bindings
# Modified (December 2008) by Matt Pierce and Anthony Theocharis,
# from code by George Tzanetakis (January, 16, 2007)

import marsyas
from numpy import array

# Create top-level patch
mng = marsyas.MarSystemManager()

def createVector(filename):

	fnet = mng.create("Series", "featureNetwork")

	# Add the MarSystems
	fnet.addMarSystem(mng.create("SoundFileSource", "src"))
	fnet.addMarSystem(mng.create("TimbreFeatures", "featExtractor"))
	fnet.addMarSystem(mng.create("TextureStats", "tStats"))
	fnet.addMarSystem(mng.create("Annotator", "annotator"))
	fnet.addMarSystem(mng.create("WekaSink", "wsink"))

	# link the controls to coordinate things
	fnet.linkControl("mrs_string/filename", "SoundFileSource/src/mrs_string/filename")
	fnet.linkControl("mrs_bool/notEmpty", "SoundFileSource/src/mrs_bool/notEmpty")
	fnet.linkControl("WekaSink/wsink/mrs_string/currentlyPlaying","SoundFileSource/src/mrs_string/currentlyPlaying")
	fnet.linkControl("Annotator/annotator/mrs_natural/label", "SoundFileSource/src/mrs_natural/currentLabel")
	fnet.linkControl("SoundFileSource/src/mrs_natural/nLabels", "WekaSink/wsink/mrs_natural/nLabels")

	# update controls to setup things
	fnet.updControl("TimbreFeatures/featExtractor/mrs_string/disableTDChild", marsyas.MarControlPtr.from_string("all"))
	fnet.updControl("TimbreFeatures/featExtractor/mrs_string/disableLPCChild", marsyas.MarControlPtr.from_string("all"))
	fnet.updControl("TimbreFeatures/featExtractor/mrs_string/disableSPChild", marsyas.MarControlPtr.from_string("all"))
	fnet.updControl("TimbreFeatures/featExtractor/mrs_string/enableSPChild", marsyas.MarControlPtr.from_string("MFCC/mfcc"))
	fnet.updControl("mrs_string/filename", marsyas.MarControlPtr.from_string(filename))
	fnet.updControl("WekaSink/wsink/mrs_string/labelNames", fnet.getControl("SoundFileSource/src/mrs_string/labelNames"))
	fnet.updControl("WekaSink/wsink/mrs_string/filename", marsyas.MarControlPtr.from_string("bextract_python.arff"))

	# do the processing extracting MFCC features and writing to weka file
	previouslyPlaying = ""
	while fnet.getControl("SoundFileSource/src/mrs_bool/notEmpty").to_bool():
		currentlyPlaying = fnet.getControl("SoundFileSource/src/mrs_string/currentlyPlaying").to_string()
		if (currentlyPlaying != previouslyPlaying):
			print "Processing: " +  fnet.getControl("SoundFileSource/src/mrs_string/currentlyPlaying").to_string()
		fnet.tick()
		previouslyPlaying = currentlyPlaying

	result = fnet.getControl("mrs_realvec/processedData").to_realvec()
	result.normMaxMin()

	result = array(result) * 100
	print result # always an array of zeroes. damn.

	return result.tolist()

