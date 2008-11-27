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


db = Database()
# delete all of the old output
for output in db.session.query(PluginOutput):
	db.session.delete(output);

# create new output!
plugins = db.session.query(Plugin).order_by(Plugin.name)
for file in db.session.query(AudioFile):
	for plugin in plugins:
		output = plugin.createVector(file);

for tag in db.session.query(Tag):
	tag.updateVector()

for file in db.session.query(AudioFile):
	for tag in file.tags:
		print file, tag, euclidean_distance(tag.vector, file.vector)
