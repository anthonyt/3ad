from model import *
import os

db = Database();

def init():

	# drop the old tables
	db.dropTables();

	# create the fresh tables
	db.createTables();

	# Create an audio file object for each file in the listings file
	# (Also dynamically create tags to represent each tag in the file)
	input = open("files.txt", 'r')
	for line in input:
		line = line.split(',')
		fname = line[0]
		if db.session.query(AudioFile).filter_by(filename=fname).count() < 1:
			# If this filename is not already existing in the database...
			f = AudioFile(fname)
			tags = filter(None, line[1].strip().split(' '))
			for tag in tags:
				tags = db.session.query(Tag).filter_by(name=tag)
				if tags.count() < 1:
					# If this tag is not already existing in the database...
					t = Tag(tag)
					db.saveObject(t)
				else:
					t = tags.all()[0]
				f.tags.append(t)
			db.saveObject(f)

	# Set up the default plugins
	plugins = [
		Plugin('charlotte', 'plugins.charlotte'),
		#Plugin('bextract', 'plugins.bextract_plugin'),
		#Plugin('centroid', 'plugins.centroid_plugin')
	]

	# Save all plugins that aren't already in the database.
	for plugin in plugins:
		if db.session.query(Plugin).filter_by(modulename=plugin.modulename).count() < 1:
			db.saveObject(plugin)
	
	# Finally, print out the data that we just entered.
	for file in db.session.query(AudioFile):
		print file, file.tags

if __name__ == "__main__":
	init()
