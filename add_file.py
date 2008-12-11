import sys
import getopt
import os
from model import *

db = Database()

def add(argv):

	# File name should be first argument
	filename = argv[0]
	if not os.path.exists(filename):
		print("ERROR: No such file exists")
		exit(2)

	# String to be written to file (will include filename and all tags)
	outstring = filename + ", "

	# Look for the tag inclusion flag
	if(len(argv) > 1):
		try:
			opts, args = getopt.getopt(argv[1:], "t:", ["tags="])
		except getopt.GetoptError:
			usage()
			sys.exit(2)
		for opt, arg in opts:
			if opt in ("-t", "--tag"):
				outstring = outstring + arg + " "

	# Update the database and files.txt with the new audio file and its corresponding filepath
	update_database(outstring)
	update_audiolist(outstring)


def update_audiolist(file_string):
	input = open("files.txt", "r+w")
	input.readlines()
	input.writelines(file_string + "\n")
	input.close()


def update_database(file_string):
	line = file_string.split(',')
	fname = line[0]
	print(fname)
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


# Usage error message
def usage():
	print("Usage: python add_file.py [filename] (optional)[-t or --tags <tag string>]")

if __name__ == "__main__":
	add(sys.argv[1:])
