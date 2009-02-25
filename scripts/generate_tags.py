import os
import getopt
import sys
from ad3.controller import controller

def main(argv):

	try:
		# Parse the command line options
		opts, args = getopt.getopt(argv[1:], "f:t:r:", ["file=", "tags=", "tolerance="])

		# Filter unique tags
		tags = " ".join(filter(None, [opt[1] for opt in opts if opt[0] in ("-t", "--tags")]))

		# use the first tolerance provided, or default to 10
		tolerances = [int(opt[1]) for opt in opts if opt[0] in ("-r", "--tolerance")]
		if len(tolerances) > 0:
			tolerance = tolerances[0]
		else:
			tolerance = 10

		# use the first file provided, or None
		files = [opt[1] for opt in opts if opt[0] in ("-f", "--file")]
		if len(files) > 0:
			filename = files[0]
		else:
			filename = None
	except getopt.GetoptError:
		usage()
		return -1

	# If no file was passed on the command line, calculate vectors and generate tags for all files currently in the database
	if filename is None:
		controller.generate_tags(None, tolerance)
		return
	else:
		# Get the file name from the command line args and check if it exists
		if not os.path.exists(filename):
			print("ERROR: '%s' No such file exists" % filename)
			return -1
		controller.generate_tags_for_file(filename, tolerance, tags)

def usage():
	print("Usage: python generate_tags.py [-f or --file=filename] [-t or --tags=tag] [-r or --tolerance=tolerance]")


if __name__ == "__main__":
	#if(len(sys.argv) < 2):
		#usage()
		#exit(-1)

	main(sys.argv)