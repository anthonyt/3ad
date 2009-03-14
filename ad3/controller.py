import sys
import os
from numpy import array, concatenate, divide, mean
from ad3.models.dht import AudioFile, Plugin, PluginOutput, Tag
from twisted.internet import defer
from functools import partial

class TagAggregator(object):
    """
    class to facilitate getting a list of tag objects from a list of tag names
    """
    def __init__(self, controller, model, tag_names, force_creation):
        self.controller = controller
        self.model = model
        self.tag_names = tag_names #list of tag names
        self.force_creation = force_creation

        self.tag_objs = []
        self.num_tags_got = 0

    def go(self, callback):
        df = defer.Deferred()
        outer_df = defer.Deferred()

        def handle_tag(val, name, t):
            # only create the missing tag if force_creation is enabled
            if t is None and self.force_creation:
                t = Tag(name)
                save_df = self.model.save(t)
            else:
                save_df = None

            if t is not None:
                self.tag_objs.append(t)

            return save_df

        def callback_wrapper(val):
            callback(self.tag_objs)

        def done(val):
            outer_df.addCallback(callback_wrapper)
            outer_df.callback('fired outer tagaggregator')

        def got_tag(name, t):
            df.addCallback(handle_tag, name, t)
            self.num_tags_got += 1
            # if this is the last tag in the lot...
            if self.num_tags_got == len(self.tag_names):
                df.addCallback(done)
                df.callback(None)

        for tag in self.tag_names:
            f = partial(got_tag, tag)
            self.model.get_tag(f, tag)

        return outer_df


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
                print "->", "Fetching vector for", tag

                def got_vector(vector):
                    print "->", "Saving vector for", tag

                    tag.vector = vector
                    self.model.save(tag)

                    num_calculated += 1
                    if num_calculated == num_tags:
                        callback()

                self.mine.calculate_tag_vector(got_vector, tag)

        self.model.get_tags(got_tags, name=tag_name)


    def create_vectors(self, callback, file_name=None, plugin_name=None):
        def got_data(files, plugins):
            for plugin in plugins:
                for file in files:
                    # FIXME: this will soon have to be asynchronous.
                    print "->", "Creating vector for", file, plugin
                    self.model.update_vector(plugin, file)

            num_files = len(files)
            num_vectors = 0

            for file in files:
                def got_file_vector(vector):
                    file.vector = vector
                    self.model.save(file)
                    print "->", "Updating vector for", file

                    # ensure that the callback function is called only on the
                    # saving of the final file vector
                    num_vectors += 1
                    if num_vectors == num_files:
                        print "->", "Updated %d plugins for %d files" % (len(plugins), len(files))
                        callback()

                self.mine.calculate_file_vector(got_file_vector, file)

        # take care of fetching the plugin and file objects...
        def got_files(files):
            def got_plugins(plugins):
                got_data(files, plugins)
            plugins = self.model.get_plugins(got_plugins, name=plugin_name)

        self.model.get_audio_files(got_files, file_name=file_name)


    def guess_tags(self, callback, audio_file=None):
        def got_data(files, tags):
            for file in files:
                for tag in tags:
                    if self.mine.does_tag_match(file, tag):
                        self.model.guess_tag_for_file(file, tag)
                        print "->", "GENERATED: ", file, tag
            callback()

        # take care of fetching the tag and audio file objects...
        def got_tags(tags):
            if audio_file is None:
                def got_files(files):
                    got_data(files, tags)
                self.model.get_audio_files(got_files)
            else:
                got_data([audio_file], tags)
        self.model.get_tags(got_tags)


    def add_file(self, callback, file_name, tags=[]):
        df = defer.Deferred()
        outer_df = defer.Deferred()
        outer_df.addCallback(callback)

        def got_file(file):
            print "\n"
            if file is None:
                file = AudioFile(file_name)

                def save_file(val):
                    save_df = self.model.save(file)
                    return save_df

                def fire_outer_df(val):
                    outer_df.callback(file)

                df.addCallback(save_file)

                if len(tags) == 0:
                    df.addCallback(fire_outer_df)
                else:
                    def got_tags(tags):
                        def apply(value, file, tag):
                            print "Attempting to apply:", tag
                            tag_df = self.model.apply_tag_to_file(file, tag)
                            return tag_df

                        for t in tags:
                            df.addCallback(apply, file, t)

                        df.addCallback(fire_outer_df)

                    def get_tags(val):
                        ta = TagAggregator(self, self.model, tags, True)
                        ta_df = ta.go(got_tags)
                        return ta_df

                    df.addCallback(get_tags)

                df.callback('fired')
            else:
                # if a matching file already exists, return None to the callback method
                # and signal outer_df as being completed.
                outer_df.callback(None)


        print "\n"
        self.model.get_audio_file(got_file, file_name=file_name)
        return outer_df


    def tag_file(self, callback, file_name, tags=[]):
        def got_file(file):
            if len(tags) == 0:
                callback(tags)
            else:
                def got_tags(tags):
                    for t in tags:
                        self.model.apply_tag_to_file(file, t)
                    callback(tags)

                ta = TagAggregator(self, self.model, tags, True)
                ta.go(got_tags)


    def add_plugin(self, callback, name, module_name):
        def got_plugin(plugin):
            if plugin is None:
                plugin = Plugin(name, module_name)
                self.model.save(plugin)
                callback(plugin)

        self.model.get_plugin(got_plugin, name=name, module_name=module_name)


    def find_files_by_tag(self, callback, tag):
        return self.model.get_audio_files(callback, guessed_tag=tag)


