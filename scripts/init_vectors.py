if __name__ == "__main__":
    import sys
    import os

    # ensure the main ad3 module is on the path
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)

    from ad3.controller import controller

    controller.regenerate_all_plugins()

