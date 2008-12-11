import os
import getopt
import sys
from controller import *

def main(argv):

	# Get the file name from the command line args and check if it exists
	filename = argv[0]
	if not os.path.exists(filename):
		print("ERROR: No such file exists")
		return -1

	# Look for the tag inclusion flag
	if(len(argv) > 1):
		try:
			opts, args = getopt.getopt(argv[1:], "t:", ["tags="])
		except getopt.GetoptError:
			usage()
			return -1
		controller.generate_tags_for_file(filename, opts)
	else:
		controller.generate_tags_for_file(filename)

def usage():
	print("Usage: python generate_tags.py [filename] (optional)[-t or --tags <user-generated tag string>]")


if __name__ == "__main__":
	if(len(sys.argv) < 2):
		usage()
		exit(-1)

	main(sys.argv[1:])
