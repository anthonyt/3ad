
# Usage error message
def usage():
    print("Usage: python add_file.py [filename] (optional)[-t or --tags <tag string>]")

if __name__ == "__main__":
    import sys
    import os

    if(len(sys.argv) < 2):
        usage()
        sys.exit(-1)

    # ensure the main ad3 module is on the path
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)

    import getopt
    from ad3.controller import controller

    args = argv[1:]

    # File name should be first argument
    filename = args[0]
    if not os.path.exists(filename):
        print("ERROR: No such file exists")
        exit(2)

    # Look for the tag inclusion flag
    if(len(args) > 1):
        try:
            opts, args = getopt.getopt(args[1:], "t:", ["tags="])
            tags = opts[0][1]
        except getopt.GetoptError:
            usage()
            sys.exit(2)
        controller.add_file(filename, tags)
    else:
        controller.add_file(filename)

