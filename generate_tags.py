import os
import getopt
import sys
from controller import *

def main(argv):

	# If no file was passed on the command line, calculate vectors and generate tags for all files currently in the database
	if(len(argv) == 1):
		controller.generate_tags(None, 80)
		return

	# Get the file name from the command line args and check if it exists
	filename = argv[1]
	if not os.path.exists(filename):
		print("ERROR: No such file exists")
		return -1

	# Look for the tag inclusion flag
	if(len(argv) > 2):
		try:
			opts, args = getopt.getopt(argv[2:], "t:", ["tags="])
			tags = opts[0][1]
		except getopt.GetoptError:
			usage()
			return -1
		controller.generate_tags_for_file(filename, tags)
	else:
		controller.generate_tags_for_file(filename)

def usage():
	print("Usage: python generate_tags.py (optional)[filename] (optional)[-t or --tags <user-generated tag string>]")


if __name__ == "__main__":
	#if(len(sys.argv) < 2):
		#usage()
		#exit(-1)

	main(sys.argv)
