import os
import getopt
import sys
from controller import *

def main(argv):
	controller.regenerate_all_plugins()
	controller.regenerate_all_tag_locations()

if __name__ == "__main__":
	#if(len(sys.argv) < 2):
		#usage()
		#exit(-1)

	main(sys.argv)
