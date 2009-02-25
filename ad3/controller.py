import sys
import getopt
import os
from numpy import array, concatenate, divide, mean
from ad3.model import Database, AudioFile, Plugin, PluginOutput, Tag

# Global framework variables
db = Database()

class controller(object):

	@staticmethod
	def regenerate_all_tag_locations():
		# Update the vector for every tag, based on the new output
		for tag in db.query(Tag):
			print "Creating vector for", tag
			tag.updateVector()
		db.commit()

	@staticmethod
	def regenerate_all_plugins(filename=None):
		# Run every plugin over every file, computing a whole bunch of Output Vectors.
		plugins = db.query(Plugin).order_by(Plugin.name)

		files = db.query(AudioFile)

		# For individual files, get the file object, then delete old PluginOutput for that file
		if filename is not None:
			files = files.filter_by(filename = filename)
			audiofile = db.query(AudioFile).filter_by(filename=filename).one()
			for old_output in db.query(PluginOutput).filter_by(file=audiofile):
				db.delete(old_output)

		if files.count() == 0:
			print "No files found with the name", filename
			return

		for plugin in plugins:
			# delete all of the old output for this plugin.
			if filename is None:
				for old_output in db.query(PluginOutput).filter_by(plugin=plugin):
					db.delete(old_output)

			# iterate over each file, generating new output.
			for file in files:
				print "Creating vector for", file, plugin
				output = plugin.createVector(file)

		db.commit()
		controller.regenerate_all_tag_locations()

	@staticmethod
	def regenerate_plugin(plugin_name):
		plugin = db.query(Plugin).filter_by(name=plugin_name).all()[0]
		# delete all of the old output for this plugin.
		for old_output in db.query(PluginOutput).filter_by(plugin=plugin):
			db.delete(old_output)

		# iterate over each file, generating new output.
		for file in db.query(AudioFile):
			print "Creating vector for", file, plugin
			output = plugin.createVector(file)

		db.commit()

		controller.regenerate_all_tag_locations()

	@staticmethod
	def generate_tags(filename=None, tolerance=None):
#		if tolerance is None:
#			tolerance  = sum([p.findMaxDistanceFromAverage() for p in db.query(Plugin)])
#			tolerance -= sum([p.findMinDistanceFromAverage() for p in db.query(Plugin)])
#		else:
#			tolerance += sum([p.findMinDistanceFromAverage() for p in db.query(Plugin)])

		print "Tolerance:", tolerance

		files = db.query(AudioFile)
		if filename is not None:
			files = files.filter_by(filename = filename)

		if files.count() == 0:
			print "No files found with the name", filename
			return

		for file in files:
			print ""
			for tag in file.tags:
				print "SEED DATA: ", file, tag
			for tag in db.query(Tag):
				if file.distanceFromTag(tag) <= tolerance:
					print "GENERATED: ", file, tag

	@staticmethod
	def add_file(filename, tagstring=""):
		if db.query(AudioFile).filter_by(filename=filename).count() < 1:
			# If this filename is not already existing in the database...
			f = AudioFile(filename)
			controller.tag_file(f, tagstring)
			db.add(f)

	@staticmethod
	def tag_file(file, tagstring):
		tags = filter(None, tagstring.strip().split(' '))
		for tag in tags:
			tags = db.query(Tag).filter_by(name=tag)
			if tags.count() < 1:
				# If this tag is not already existing in the database...
				t = Tag(tag)
				db.add(t)
			else:
				t = tags.all()[0]
			if t not in file.tags:
				file.tags.append(t)

		db.commit()

	@staticmethod
	def add_plugin(name, modulename):
		query = db.query(Plugin).filter_by(modulename=modulename)
		if query.count() < 1:
			plugin = Plugin(name, modulename)
			db.add(plugin)
			db.commit()
		return query.one()


	@staticmethod
	def generate_tags_for_file(filename, tolerance, tagstring=""):
		# Check to see if this filename already exists in the database
		query = db.query(AudioFile).filter_by(filename=filename)
		if query.count() < 1:
			# If not already existing in the database, run the add_file script to create a new object
			file = controller.add_file(filename, tagstring)
			# Run all active plugins over the newly generated file and obtain tag generation results
			controller.regenerate_all_plugins(filename)
		else:
			file = query.all()[0]

		controller.tag_file(file, tagstring)
		controller.regenerate_all_tag_locations()
		controller.generate_tags(filename, tolerance)

