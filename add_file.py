import marsyas
import sys
import getopt
import os

def main(argv):

	# File name should be first argument
	filename = argv[0]

	# String to be written to file (will include filename and all tags)
	outstring = "audio/" + filename + ", "

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

	# Append the new file name (and tag if specified) to the files list
	input = open("files.txt", "r+w")
	input.readlines()
	input.writelines(outstring + "\n")

	input.close()

def usage():
	print("Usage: python add_file.py [filename] (optional)[-t or --tags <tag string>]")

if __name__ == "__main__":
	main(sys.argv[1:])
