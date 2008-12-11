import os
import getopt
import sys
from controller import *

def main(argv):
	controller.regenerate_all_plugins()

if __name__ == "__main__":
	main(sys.argv)
