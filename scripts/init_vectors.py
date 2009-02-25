import os
import getopt
import sys
from ad3.controller import controller

def main(argv):
	controller.regenerate_all_plugins()

if __name__ == "__main__":
	main(sys.argv)
