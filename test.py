from model import *
from numpy import array, concatenate, divide, mean

# instantiate our database handle
db = Database()

def euclidean_distance(a, b):
	"""
	takes two numpy arrays, a, b, both of length n
	returns the magnitude of the distance between them (float)
	"""
	c = a - b
	sum_of_squares = dot(c,c)
	return sqrt(sum_of_squares)

def regenerate_all_tag_locations():
	# Update the vector for every tag, based on the new output
	for tag in db.session.query(Tag):
		print "Creating vector for", tag
		tag.updateVector()

def regenerate_all_plugins():
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

	regenerate_all_tag_locations();

def regenerate_plugin(plugin_name):
	plugin = db.session.query(Plugin).filter_by(name=plugin_name).all()[0]
	# delete all of the old output for this plugin.
	for old_output in db.session.query(PluginOutput).filter_by(plugin=plugin):
		db.session.delete(old_output)

	# iterate over each file, generating new output.
	for file in db.session.query(AudioFile):
		print "Creating vector for", file, plugin
		output = plugin.createVector(file);

	regenerate_all_tag_locations();

def generate_tags(tolerance=None):
	for file in db.session.query(AudioFile):
		print ""
		for tag in file.tags:
			print "SEED DATA: ", file, tag
		for tag in db.session.query(Tag):
			if tolerance is not None:
				if euclidean_distance(tag.vector, file.vector) <= tolerance:
					print "GENERATED: ", file, tag

regenerate_all_plugins()
regenerate_all_tag_locations()
generate_tags(10)
