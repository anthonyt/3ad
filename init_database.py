from model import *
import os

db = Database();

# create the table
db.createTables();

# Populate it with our initial data.
# First, some tags
tags = [
	Tag("strings"),
	Tag("cello")
]

# Save all of the tags that don't already exist in the database.
for tag in tags:
	if db.session.query(Tag).filter_by(name=tag.name).count() < 1:
		db.saveObject(tag)

# Create an audio file object for each file in the audio directory
input = open("files.txt", 'r')
for line in input:
	line = line.split(',')
	fname = line[0]
	if db.session.query(AudioFile).filter_by(filename=fname).count() < 1:
		f = AudioFile(fname)
		tags = filter(None, line[1].strip().split(' '))
		for tag in tags:
			tags = db.session.query(Tag).filter_by(name=tag)
			if tags.count() < 1:
				t = Tag(tag)
				db.saveObject(t)
			else:
				t = tags.all()[0]
			f.tags.append(t)
		db.saveObject(f)

#files = [AudioFile('audio/'+f) for f in os.listdir('./audio/')]

#for file in files:
#	if db.session.query(AudioFile).filter_by(filename=file.filename).count() < 1:
#		db.saveObject(file)

# Third, set up the default plugins
plugins = [
	Plugin('charlotte', 'plugins.charlotte')
]

# Save all plugins that aren't already in the database.
for plugin in plugins:
	if db.session.query(Plugin).filter_by(modulename=plugin.modulename).count() < 1:
		db.saveObject(plugin)

# Finally, print out the data that we just entered.
for file in db.session.query(AudioFile):
	print file, file.tags
