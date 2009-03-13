import sys
import getopt
import os
from numpy import array, concatenate, divide, mean
from ad3.models.dht import AudioFile, Plugin, PluginOutput, Tag

class Controller(object):

    def __init__(self, data_model, learning_algorithm):
        self.model = data_model
        self.mine = learning_algorithm

    def initialize_storage(self, callback):
        self.model.initialize_storage(callback)

    def update_tag_vectors(self, callback, tag_name = None):
        # Update the vector for every tag, based on the new output
        def got_tags(tags):
            num_tags = len(tags)
            num_calculated = 0

            for tag in tags:
                print "Fetching vector for", tag

                def got_vector(vector):
                    print "Saving vector for", tag

                    tag.vector = vector
                    self.model.save(tag)

                    num_calculated += 1
                    if num_calculated == num_tags:
                        callback()

                self.mine.calculate_tag_vector(got_vector, tag)

        return self.model.get_tags(got_tags, name=tag_name)


    def create_vectors(self, callback, file_name=None, plugin_name=None):
        def got_data(files, plugins):
            for plugin in plugins:
                for file in files:
                    # FIXME: this will soon have to be asynchronous.
                    print "Creating vector for", file, plugin
                    self.model.update_vector(plugin, file)

            num_files = len(files)
            num_vectors = 0

            for file in files:
                def got_file_vector(vector):
                    file.vector = vector
                    self.model.save(file)
                    print "Updating vector for", file

                    # ensure that the callback function is called only on the
                    # saving of the final file vector
                    num_vectors += 1
                    if num_vectors == num_files:
                        print "Updated %d plugins for %d files" % (len(plugins), len(files))
                        callback()

                self.mine.calculate_file_vector(got_file_vector, file)

        # take care of fetching the plugin and file objects...
        def got_files(files):
            def got_plugins(plugins):
                got_data(files, plugins)
            plugins = self.model.get_plugins(got_plugins, name=plugin_name)

        return self.model.get_audio_files(got_files, file_name=file_name)


    def guess_tags(self, callback, audio_file=None):
        def got_data(files, tags):
            for file in files:
                for tag in tags:
                    if self.mine.does_tag_match(file, tag):
                        self.model.guess_tag_for_file(file, tag)
                        print "GENERATED: ", file, tag
            callback()

        # take care of fetching the tag and audio file objects...
        def got_tags(tags):
            if audio_file is None:
                def got_files(files):
                    got_data(files, tags)
                self.model.get_audio_files(got_files)
            else:
                got_data([audio_file], tags)
        return self.model.get_tags(got_tags)


    def add_file(self, callback, file_name, tags=[]):
        def got_file(file):
            if file is None:
                file = AudioFile(file_name)
                self.model.save(file)

                if len(tags) == 0:
                    callback(file)
                else:
                    num_tags = len(tags)
                    num_tagged = 0

                    for tag in tags:
                        def got_tag(t):
                            if t is None:
                                t = Tag(tag)
                                self.model.save(t)
                            self.model.apply_tag_to_file(f, t)

                            # call the callback after applying the final tag.
                            num_tagged += 1
                            if num_tagged == num_tags:
                                callback(file)

                        self.model.get_tag(got_tag, tag)


        return self.model.get_audio_file(got_file, file_name=file_name)


    def tag_file(self, callback, file_name, tags=[]):
        # accomodate tags lists that are in string format
        if type(tags) is unicode:
            tags = filter(lambda x: x != u'', tags.strip().split(u' '))

        if type(file_name) is unicode:
            file = self.model.get_audio_file(file_name)
        else:
            file = file_name

        for _tag in tags:
            tag = self.model.get_tag(_tag)

            if tag is None:
                tag = Tag(_tag)
                self.model.save(tag)

            if tag not in file.tags:
                file.tags.append(tag)
            self.model.save(file)


    def add_plugin(self, callback, name, module_name):
        def got_plugin(plugin):
            if plugin is None:
                plugin = Plugin(name, module_name)
                self.model.save(plugin)
                callback(plugin)

        return self.model.get_plugin(got_plugin, name=name, module_name=module_name)


    def find_files_by_tag(self, callback, tag):
        return self.model.get_audio_files(callback, guessed_tag=tag)


