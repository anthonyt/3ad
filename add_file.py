import sys
import getopt
import os
from controller import *

db = Database()

def main(argv):

	# File name should be first argument
	filename = argv[0]
	if not os.path.exists(filename):
		print("ERROR: No such file exists")
		exit(2)

	# Look for the tag inclusion flag
	if(len(argv) > 1):
		try:
			opts, args = getopt.getopt(argv[1:], "t:", ["tags="])
		except getopt.GetoptError:
			usage()
			sys.exit(2)
		controller.add_file(filename, opts)
	else:
		controller.add_file(filename)


# Usage error message
def usage():
	print("Usage: python add_file.py [filename] (optional)[-t or --tags <tag string>]")

if __name__ == "__main__":
	if(len(sys.argv) < 2):
		usage()
		return -1
		
	main(sys.argv[1:])
