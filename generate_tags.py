import os
import getopt
import sys
import add_file
import init_database
import test
from model import *

db = Database()

def main(argv):

	# Get the file name from the command line args and check if it exists
	fname = argv[0]
	if not os.path.exists(fname):
		print("ERROR: No such file exists")
		exit(2)

	# Check to see if this filename already exists in the database
	if db.session.query(AudioFile).filter_by(filename=fname).count() < 1:
		# If not already existing in the database, run the add_file script to create a new object
		add_file.add(argv)

	# Run all active plugins over the newly generated file and obtain tag generation results
	test.regenerate_all_plugins(fname)
	test.regenerate_all_tag_locations()
	test.generate_tags(fname, 80)


def usage():
	print("Usage: python generate_tags.py [filename] (optional)[-t or --tags <user-generated tag string>]")


if __name__ == "__main__":
	if(len(sys.argv) < 2):
		usage()
		exit(2)

	main(sys.argv[1:])
