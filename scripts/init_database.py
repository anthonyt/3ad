from ad3.model import AudioFile, Plugin
from ad3.controller import db, controller
import os

def init():

	# drop the old tables
	db.dropTables();

	# create the fresh tables
	db.createTables();

	# Create an audio file object for each file in the listings file
	# (Also dynamically create tags to represent each tag in the file)
	input = open("files.txt", 'r')
	for line in input:
		(fname, tagstring) = line.split(",")
		controller.add_file(fname, tagstring)

	# Set up the default plugins
	plugins = [
		('charlotte', 'plugins.charlotte'),
		#('bextract', 'plugins.bextract_plugin'),
		#('centroid', 'plugins.centroid_plugin')
	]

	# Save all plugins that aren't already in the database.
	for plugin in plugins:
		controller.add_plugin(plugin[0], plugin[1])


	# Finally, print out the data that we just entered.
	for file in db.query(AudioFile):
		print file, file.tags
	for plugin in db.query(Plugin):
		print plugin

if __name__ == "__main__":
	init()
