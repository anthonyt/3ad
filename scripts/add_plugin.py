import sys
from ad3.controller import controller

def main(argv=sys.argv):
	name = argv[1]
	modulename = argv[2]

	try:
		plugin = controller.add_plugin(name, modulename)
		print "Created Plugin: ", plugin
		return 0
	except ImportError:
		print "Cannot find module ", modulename
		return 1

if __name__ == "__main__":
	sys.exit(main())
