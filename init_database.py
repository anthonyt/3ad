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
	AudioFile("Cello note a.wav"),
	AudioFile("Cello note c.wav"),
	AudioFile("Cello note g.wav")
]

for file in files:
	for tag in tags:
		file.tags.append(tag)
	db.saveObject(file)

# print out the data that we just entered.
for file in db.session.query(AudioFile):
	print file, file.tags
