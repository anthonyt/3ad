from model import *
from numpy import array, concatenate, divide, mean

def euclidean_distance(a, b):
	"""
	takes two numpy arrays, a, b, both of length n
	returns the magnitude of the distance between them (float)
	"""
	c = a - b
	sum_of_squares = dot(c,c)
	return sqrt(sum_of_squares)

# instantiate our database handle
db = Database()

# Run every plugin over every file, computing a whole bunch of Output Vectors.
plugins = db.session.query(Plugin).order_by(Plugin.name)
for plugin in plugins:
	# delete all of the old output for this plugin.
	for old_output in db.session.query(PluginOutput).filter_by(plugin=plugin):
		db.session.delete(old_output)

	# iterate over each file, generating new output.
	for file in db.session.query(AudioFile):
		print "Creating vector for", file, plugin
		output = plugin.createVector(file);

# Update the vector for every tag, based on the new output
for tag in db.session.query(Tag):
	print "Creating vector for", tag
	tag.updateVector()

# Calculate the distance of each file from each tag that it as associated with.
# then print it.
for file in db.session.query(AudioFile):
	print ""
	for tag in db.session.query(Tag):
		print file, tag, euclidean_distance(tag.vector, file.vector)
