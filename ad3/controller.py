import sys
import getopt
import os
from numpy import array, concatenate, divide, mean
from ad3.models.sql import Database, AudioFile, Plugin, PluginOutput, Tag

class Controller(object):

    def __init__(self, data_model, learning_algorithm):
        self.model = data_model
        self.mine = learning_algorithm

    def initialize_storage(self):
        self.model.initialize_storage()

    def update_tag_vectors(self, tag_name = None):
        # Update the vector for every tag, based on the new output
        for tag in self.model.get_tags(name = tag_name):
            print "Creating vector for", tag
            vector = self.mine.calculate_tag_vector(tag)
            tag.vector = vector
            self.model.save(tag)


    def create_vectors(self, file_name=None, plugin_name=None):
        # When called without any arguments, regenerates all plugins for all files.
        plugins = self.model.get_plugins(name=plugin_name)
        files = self.model.get_audio_files(file_name=file_name)

        # update all the plugin outputs
        for plugin in plugins:
            for file in files:
                print "Creating vector for", file, plugin
                vector = self.model.update_vector(plugin, file)

        # update the file vectors
        for file in files:
            file.vector = self.mine.calculate_file_vector(file)

        print "Updated %d plugins for %d files" % (len(plugins), len(files))


    def guess_tags(self, file_name=None):
        files = self.model.get_audio_files(file_name=file_name)
        tags = self.model.get_tags()

        for file in files:
            for tag in tags:
                if self.mine.does_tag_match(file.file_name, tag.name):
                    file.generated_tags.append(tag)
                    self.model.save(file)
                    print "GENERATED: ", file, tag


    def add_file(self, file_name, tags=[]):
        files = self.model.get_audio_files(file_name=file_name)
        if len(files) < 1:
            # If this file_name is not already existing in the database...
            f = AudioFile(file_name)
            self.tag_file(f, tags)
            self.model.save(f)


    def tag_file(self, file_name, tags=[]):
        # accomodate tags lists that are in string format
        if type(tags) is unicode:
            tags = filter(lambda x: x != u'', tags.strip().split(u' '))

        if type(file_name) is unicode:
            file = self.model.get_audio_file(file_name)
        else:
            file = file_name

        for tag in tags:
            tag = self.model.get_tag(tag)
            if tag not in file.tags:
                file.tags.append(tag)
            self.model.save(file)


    def add_plugin(self, name, module_name):
        plugins = self.model.get_plugins(name = name, module_name = module_name)
        if len(plugins) < 1:
            plugin = Plugin(name, module_name)
            self.model.save(plugin)


    def find_files_by_tag(self, tags):
        return self.model.get_files(tags=tags, include_guessed=True)

