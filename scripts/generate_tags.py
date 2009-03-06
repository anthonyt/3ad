
def usage():
    print("Usage: python generate_tags.py [-f or --file=filename] [-t or --tags=tag] [-r or --tolerance=tolerance]")


if __name__ == "__main__":
    import sys
    import os

    # ensure the main ad3 module is on the path
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)

    import getopt
    import ad3.models.sql
    from ad3.learning.euclid import Euclidean
    from ad3.controller import Controller

    model = ad3.models.sql
    euclid = Euclidean(model)
    controller = Controller(model, euclid)

    try:
        # Parse the command line options
        opts, args = getopt.getopt(sys.argv[1:], "f:t:r:", ["file=", "tags=", "tolerance="])

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
        filename = None

        if len(files) > 0:
            filename = files[0]

    except getopt.GetoptError:
        usage()
        sys.exit(1)

    # If no file was passed on the command line, calculate vectors and generate tags for all files currently in the database
    if filename is not None:
        # Get the file name from the command line args and check if it exists
        if not os.path.exists(filename):
            print("ERROR: '%s' No such file exists" % filename)
            sys.exit(1)

    controller.guess_tags(filename)
    sys.exit(0)

