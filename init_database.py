
from database import *

metadata.create_all(engine)


tags = [
	Tag("strings"),
	Tag("cello")
]

files = [
	AudioFile("Cello note a.wav"),
	AudioFile("Cello note c.wav"),
	AudioFile("Cello note g.wav")
]

for tag in tags:
	session.save(tag)

for file in files:
	for tag in tags:
		file.tags.append(tag)
	session.save(file)

for file in session.query(AudioFile):
	print file, file.tags
