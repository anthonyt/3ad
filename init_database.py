from model import *

db = Database();

# create the table
db.createTables();

# Populate it with our initial data.
# First, some tags
tags = [
	Tag("strings"),
	Tag("cello")
]

for tag in tags:
	db.saveObject(tag)

# Second, our demo files
files = [
	AudioFile("audio/Cello note a.wav"),
	AudioFile("audio/Cello note c.wav"),
	AudioFile("audio/Cello note g.wav")
#### ADD MORE AUDIO FILES HERE. THEN WE CAN TEST THE EUCLIDEAN DISTANCES
#### FROM THE STRINGS TAGS WITH THE TEST SCRIPT. WHEE
]

for file in files:
	for tag in tags:
		file.tags.append(tag)
	db.saveObject(file)

# Third, set up the default plugins
plugins = [
	Plugin('charlotte', 'plugins.charlotte')
]

for plugin in plugins:
	db.saveObject(plugin)

# Finally, print out the data that we just entered.
for file in db.session.query(AudioFile):
	print file, file.tags
