import sys
from model import *

def main(argv=sys.argv):
	name = argv[1]
	modulename = argv[2]
	db = Database()

	try:
		plugin = Plugin(name, modulename)
		db.saveObject(plugin)
		print "Created Plugin: ", plugin
		return 0
	except ImportError:
		print "Cannot find module ", modulename
		return 1

if __name__ == "__main__":
	sys.exit(main())
