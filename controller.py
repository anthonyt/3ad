import sys
import getopt
import os
from model import *
import test

# Global framework variables
db = Database()
tolerance = 80

class controller(object):


	def add_file(filename, opts=None):
		# String to be written to file or db (will include filename and all tags)
		outstring = filename + ", "

		if opts is not None:
			for opt, arg in opts:
				if opt in ("-t", "--tag"):
					outstring = outstring + arg + " "

		# Update the database and files.txt with the new audio file and its corresponding filepath
		add_file_to_db(outstring)
		add_filepath_to_audiolist(outstring)


	def add_file_to_db(file_string):
		input = open("files.txt", "r+w")
		input.readlines()
		input.writelines(file_string + "\n")
		input.close()


	def add_filepath_to_audiolist(file_string):
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


	def generate_tags_for_file(filename, opts):
		# Check to see if this filename already exists in the database
		if db.session.query(AudioFile).filter_by(filename=filename).count() < 1:
			# If not already existing in the database, run the add_file script to create a new object
			add_file(filename, opts)

		# Run all active plugins over the newly generated file and obtain tag generation results
		test.regenerate_all_plugins(filename)
		test.regenerate_all_tag_locations()
		test.generate_tags(filename, tolerance)
