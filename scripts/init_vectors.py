if __name__ == "__main__":
    import sys
    import os

    # ensure the main ad3 module is on the path
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)

    import ad3.models.sql
    from ad3.learning.euclid import Euclidean
    from ad3.controller import Controller

    model = ad3.models.sql
    euclid = Euclidean(model)
    controller = Controller(model, euclid)

#    controller.create_vectors()
    controller.update_tag_vectors()

