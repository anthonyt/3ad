from model import *

db = Database()

# delete all of the old output
for output in db.session.query(PluginOutput):
	db.session.delete(output);

# create new output!
for file in db.session.query(AudioFile):
	for plugin in db.session.query(Plugin):
		output = plugin.createVector(file);
		print output

