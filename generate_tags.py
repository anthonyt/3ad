import os
import getopt
import sys
import add_file
import init_database
import test
from model import *

db = Database()

def main(argv):
	
	fname = argv[0]

	# Check to see if this filename already exists in the database
	if db.session.query(AudioFile).filter_by(filename=fname).count() < 1:
		# If not already existing in the database, run the add_file script to create a new object
		add_file.main(argv)
	
	test.regenerate_all_plugins(fname)

def usage():
	print("Usage: python generate_tags.py [filename] (optional)[-t or --tags <user-generated tag string>]")

if __name__ == "__main__":

	print(len(sys.argv))
	if(len(sys.argv) < 2):
		usage()
		exit(2)

	main(sys.argv[1:])
