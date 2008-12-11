import sys
import getopt
import os
from numpy import array, concatenate, divide, mean
from model import *
import test

# Global framework variables
db = Database()
tolerance = 80

class controller(object):

	@staticmethod
	def regenerate_all_tag_locations():
		# Update the vector for every tag, based on the new output
		for tag in db.session.query(Tag):
			print "Creating vector for", tag
			tag.updateVector()

	@staticmethod
	def regenerate_all_plugins(filename=None):
		# Run every plugin over every file, computing a whole bunch of Output Vectors.
		plugins = db.session.query(Plugin).order_by(Plugin.name)

		files = db.session.query(AudioFile)

		# For individual files, get the file object, then delete old PluginOutput for that file
		if filename is not None:
			files = files.filter_by(filename = filename)
			audiofile = db.session.query(AudioFile).filter_by(filename=filename).one()
			for old_output in db.session.query(PluginOutput).filter_by(file=audiofile):
				db.session.delete(old_output)

		if files.count() == 0:
			print "No files found with the name", filename
			return
		
		for plugin in plugins:
			# delete all of the old output for this plugin.
			if filename is None:
				for old_output in db.session.query(PluginOutput).filter_by(plugin=plugin):
					db.session.delete(old_output)

			# iterate over each file, generating new output.
			for file in files:
				print "Creating vector for", file, plugin
				output = plugin.createVector(file)

	@staticmethod
	def regenerate_plugin(plugin_name):
		plugin = db.session.query(Plugin).filter_by(name=plugin_name).all()[0]
		# delete all of the old output for this plugin.
		for old_output in db.session.query(PluginOutput).filter_by(plugin=plugin):
			db.session.delete(old_output)
	
		# iterate over each file, generating new output.
		for file in db.session.query(AudioFile):
			print "Creating vector for", file, plugin
			output = plugin.createVector(file);

		regenerate_all_tag_locations();

	@staticmethod
	def generate_tags(filename=None, tolerance=None):
		if tolerance is None:
			tolerance  = sum([p.findMaxDistanceFromAverage() for p in db.session.query(Plugin)])
			tolerance -= sum([p.findMinDistanceFromAverage() for p in db.session.query(Plugin)])
		else:
			tolerance += sum([p.findMinDistanceFromAverage() for p in db.session.query(Plugin)])

		print "Tolerance:", tolerance

		files = db.session.query(AudioFile)
		if filename is not None:
			files = files.filter_by(filename = filename)

		if files.count() == 0:
			print "No files found with the name", filename
			return

		for file in files:
			print ""
			for tag in file.tags:
				print "SEED DATA: ", file, tag
			for tag in db.session.query(Tag):
				if file.distanceFromTag(tag) <= tolerance:
					print "GENERATED: ", file, tag

	@staticmethod
	def add_file(filename, opts=None):

		# If the file already exists, return, there is no need to re-add
		if db.session.query(AudioFile).filter_by(filename=filename).count() > 0:
			for old_output in db.session.query(PluginOutput).filter_by(filename=filename):
				print "in here"
				db.session.delete(old_output)
			return

		# String to be written to file or db (will include filename and all tags)
		outstring = filename + ", "

		# Add tags to string
		if opts is not None:
			for opt, arg in opts:
				if opt in ("-t", "--tag"):
					outstring = outstring + arg + " "

		# Update the database and files.txt with the new audio file and its corresponding filepath
		controller.add_file_to_db(outstring)
		controller.add_filepath_to_audiolist(outstring)

	@staticmethod
	def add_filepath_to_audiolist(file_string):
		input = open("files.txt", "r+w")
		input.readlines()
		input.writelines(file_string + "\n")
		input.close()

	@staticmethod
	def add_file_to_db(file_string):
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

	@staticmethod
	def generate_tags_for_file(filename, opts=None):
		# Check to see if this filename already exists in the database
		if db.session.query(AudioFile).filter_by(filename=filename).count() < 1:
			# If not already existing in the database, run the add_file script to create a new object
			controller.add_file(filename, opts)

		# Run all active plugins over the newly generated file and obtain tag generation results
		controller.regenerate_all_plugins(filename)
		controller.regenerate_all_tag_locations()
		print filename
		controller.generate_tags(filename, tolerance)
