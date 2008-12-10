from marsyas import *
from numpy import array

mng = MarSystemManager()

def createVector(filename):

	# Create the centroid network
	net = mng.create("Series/net")
	net.addMarSystem(mng.create("SoundFileSource/src"))
	net.addMarSystem(mng.create("Windowing/ham"))
	net.addMarSystem(mng.create("Spectrum/spk"))
	net.addMarSystem(mng.create("PowerSpectrum/pspk"))
	net.addMarSystem(mng.create("Centroid/cntrd"))
	net.addMarSystem(mng.create("Memory/mem"))
	net.addMarSystem(mng.create("Mean/mean"))

	# Update the filename control for the centroid network
	net.updControl("SoundFileSource/src/mrs_string/filename", filename)

	# Loop through the audio file until it reaches the end
	while (net.getctrl("SoundFileSource/src/mrs_bool/notEmpty").to_bool()):

		# Tick the audio samples with each loop
		net.tick()

		# Obtain centroid values for this frame
		result = net.getctrl("mrs_realvec/processedData").to_realvec()

	result.normMaxMin()
	result = array(result) * 100

	return result.tolist()
