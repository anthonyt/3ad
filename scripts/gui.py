#!/usr/bin python

import pygtk
pygtk.require('2.0')
import gtk

import os
import test

class gui:

    def print_message(self, widget, data):
        print "%s button was pressed" % data
        if data == "Process":
            test.regenerate_all_plugins()
            test.regenerate_all_tag_locations()
            test.generate_tags(80)

    # Return false on a GTK delete_event to create a destroy event and quit the program
    def delete_event(self, widget, event, data=None):
        gtk.main_quit()
        return False

    # Quit the program on a GTK destroy event
    def destroy(self, widget, data=None):
        gtk.main_quit()

    def __init__(self):
        # Set initial window parameters
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("3AD Framework");
        self.window.connect("delete_event", self.delete_event)
        self.window.connect("destroy", self.destroy)
        self.window.set_border_width(10)
        self.window.set_default_size(1400, 750)

        # Set a box to pack buttons into
        button_box = gtk.VBox(False, 0)
        self.window.add(button_box)

        # Create the first button and pack it into the button_box
        self.button1 = gtk.Button("File")
        self.button1.connect("clicked", self.print_message, "File")
        button_box.pack_start(self.button1, False, False, 0)
        self.button1.show()

        # Create the second button and pack it into the button_box
        self.button2 = gtk.Button("Process")
        self.button2.connect("clicked", self.print_message, "Process")
        button_box.pack_start(self.button2, False, False, 0)
        self.button2.show()

        button_box.show()

        self.window.show()

    def main(self):
        gtk.main()

print __name__

if __name__ == "__main__":
    g = gui()
    g.main()

