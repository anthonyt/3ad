import sys
import os
from numpy import array, concatenate, divide, mean
from ad3.models.dht import AudioFile, Plugin, PluginOutput, Tag
from twisted.internet import defer
from functools import partial
from sets import Set

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

class FileAggregator(object):
    def __init__(self, controller, model, tag_list, user_name=None):
        self.controller = controller
        self.model = model
        self.tag_list = tag_list #list of tag objects
        self.user_name = user_name

        self.num_got_files = 0
        self.file_lists = {}

    def go(self, callback):
        outer_df = defer.Deferred()
        outer_df.addCallback(callback)

        def got_all_files():
            # find the Set of files such that every file belongs to every tag
            files = None
            for tag_name in self.file_lists:
                if files is None:
                    #print self.file_lists[tag_name]
                    files = Set(self.file_lists[tag_name])
                else:
                    files = files.intersection(self.file_lists[tag_name])

            # start the callback chain
            outer_df.callback(list(files))

        def got_files(tag_name, files):
            if files is not None:
                self.file_lists[tag_name].extend(files)
            self.num_got_files += 1

            # if we have got all the values we asked for,
            # find the common keys, and call the callback function
            if self.num_got_files == 2*len(self.tag_list):
                got_all_files()


        if len(self.tag_list) < 1:
            outer_df.addCallback(callback_wrapper, [])
            outer_df.callback(None)
        else:
            for tag in self.tag_list:
                self.file_lists[tag.name] = []
                self.model.get_audio_files(partial(got_files, tag.name), tag=tag, user_name=self.user_name)
                self.model.get_audio_files(partial(got_files, tag.name), guessed_tag=tag, user_name=self.user_name)

        return outer_df


class Controller(object):

    def __init__(self, data_model, learning_algorithm):
        self.model = data_model
        self.mine = learning_algorithm

    def initialize_storage(self, callback):
        self.model.initialize_storage(callback)

    def update_tag_vectors(self, callback, tag_name = None):
        outer_df = defer.Deferred()
        outer_df.addCallback(callback)

        df = defer.Deferred()

        # Update the vector for every tag, based on the new output
        def got_tags(tags):
            c = [0]
            def got_vector(tag, vector):
                tag.vector = vector
                def save_tag(val):
                    #print "->", "Saving vector for", tag
                    s_df = self.model.save(tag)
                    return s_df

                df.addCallback(save_tag)

                c[0] += 1
                # track the iteration. if this is the last one, trigger the outer_df
                if c[0] == len(tags):
                    df.addCallback(outer_df.callback)

            for tag in tags:
                def get_vector(val, tag):
                    #print "->", "Fetching vector for", tag
                    cb = partial(got_vector, tag)
                    t_df = self.mine.calculate_tag_vector(cb, tag)
                    return t_df
                df.addCallback(get_vector, tag)

            df.callback(None)

        self.model.get_tags(got_tags, name=tag_name)

        return outer_df


    def create_vectors(self, file, plugin_name=None):
        outer_df = defer.Deferred()
        #    get_plugins
        # -> got_plugins
        # -> update_plugin_vector (for each plugin)
        # -> calculate_file_vector
        # -> got_file_vector (save file)
        # -> outer_df.callback

        def calculate_file_vector(val):
            # this deferred will pass the calculated vector onto the next callback
            df = self.mine.calculate_file_vector(file)
            return df

        def got_plugins(plugins):
            deferreds = []
            for plugin in plugins:
                #print "->", "Creating vector for", file, plugin
                df = self.model.update_vector(plugin, file)
                deferreds.append(df)

            df_list = defer.DeferredList(deferreds, consumeErrors=1)
            df_list.addCallback(calculate_file_vector)
            df_list.addCallback(outer_df.callback)

        self.model.get_plugins(got_plugins, name=plugin_name)

        return outer_df



    def guess_tags(self, callback, audio_file=None, user_name=None):
        df = defer.Deferred()
        outer_df = defer.Deferred()
        outer_df.addCallback(callback)

        def guess_tag(val, file, tag):
            df = self.model.guess_tag_for_file(file, tag)
            return df

        def got_data(tags, files):
            for file in files:
                for tag in tags:
                    if self.mine.does_tag_match(file, tag):
                        #print "->", "GENERATED: ", file, tag
                        df.addCallback(guess_tag, file, tag)

            df.addCallback(outer_df.callback)

        def got_tags(tags):
            # take care of fetching the tag and audio file objects...
            if audio_file is None:
                self.model.get_audio_files(partial(got_data, tags), user_name=user_name)
            else:
                got_data(tags, [audio_file])

        def get_tags(val):
            self.model.get_tags(got_tags)

        def remove_old(val):
            df = self.model.remove_guessed_tags()
            return df

        df.addCallback(remove_old)
        df.addCallback(get_tags)
        df.callback(None)

        return outer_df

    def add_files(self, file_names, user_name, tags=None):
        outer_df = defer.Deferred()
        file_save_df = defer.Deferred()
        file_save_df.callback(None)

        num_files = len(file_names) - 1
        num_got = [0]
        result_tuples = {}

        def done(val):
            print "Calling back outer_df with", result_tuples
            outer_df.callback(result_tuples)

        if tags is None:
            tags = []

        def got_file(file_name, file):
            last_one = False

            if file is not None:
                # file already exists
                result_tuples[file_name] = (file, False)
            else:
                # make a new file!
                file = AudioFile(file_name, user_name=user_name)
                result_tuples[file_name] = (file, True)

                def save_file(val):
                    print "--> Saving", file_name
                    if last_one:
                        print "--------- lastone callback'd!"
                        file_save_df.addCallback(done)

                    save_df = self.model.save(file)
                    return save_df

                def apply_vector(vector):
                    print "--> Applying vector to ", file_name, vector
                    file.vector = vector

                    # return a reference to the save_file function
                    return save_file

                df = defer.Deferred()
                df.addCallback(self.create_vectors) # passes the vector to the next callback
                df.addCallback(apply_vector) # passes the save function to the next callback
                df.addCallback(file_save_df.addCallback) # append our save function to the queue

                if len(tags) > 0:
                    def got_tags(tags):
                        def apply(value, file, tag):
                            print "Attempting to apply:", tag, "to", file
                            tag_df = self.model.apply_tag_to_file(file, tag)
                            return tag_df

                        for t in tags:
                            file_save_df.addCallback(apply, file, t)

                    def get_tags(val):
                        ta = TagAggregator(self, self.model, tags, True)
                        ta_df = ta.go(got_tags)
                        return ta_df

                    file_save_df.addCallback(get_tags)

                # Pass "file" to our first callback
                df.callback(file)

            # If this is the last iteration...
            last_one = (num_got[0] >= num_files)
            num_got[0] += 1

            if last_one:
                print "--> LAST ONE! num_got =", num_got[0]

        for file_name in file_names:
            print "Getting audio file..."
            self.model.get_audio_file(partial(got_file, file_name), file_name=file_name, user_name=user_name)

        return outer_df



    def add_file(self, callback, file_name, user_name=None, tags=None):
        df = defer.Deferred()
        outer_df = defer.Deferred()
        outer_df.addCallback(callback)

        if tags is None:
            tags = []

        def got_file(file):
            if file is None:
                file = AudioFile(file_name, user_name=user_name)

                def save_file(vector):
                    file.vector = vector
                    save_df = self.model.save(file)
                    return save_df

                def lmk(vector):
                    print "LETTING YOU KNOW THAT VECTORS HAVE BEEN CREATED"
                    return vector

                def done(val):
                    outer_df.callback((file, True))

                df.addCallback(self.create_vectors)
                df.addCallback(lmk)
                df.addCallback(save_file)

                if len(tags) == 0:
                    df.addCallback(done)
                else:
                    def got_tags(tags):
                        def apply(value, file, tag):
                            #print "Attempting to apply:", tag
                            tag_df = self.model.apply_tag_to_file(file, tag)
                            return tag_df

                        for t in tags:
                            df.addCallback(apply, file, t)

                        df.addCallback(done)

                    def get_tags(val):
                        ta = TagAggregator(self, self.model, tags, True)
                        ta_df = ta.go(got_tags)
                        return ta_df

                    df.addCallback(get_tags)

                # Pass "file" to our first callback
                df.callback(file)
            else:
                # if a matching file already exists, return None to the callback method
                # and signal outer_df as being completed.
                outer_df.callback((file, False))


        #print "\n"
        self.model.get_audio_file(got_file, file_name=file_name, user_name=user_name)
        return outer_df


    def tag_files(self, callback, file_list, tag_names=[]):
        outer_df = defer.Deferred()
        outer_df.addCallback(callback)

        def apply_tag(val, file, tag):
            a_df = self.model.apply_tag_to_file(file, tag)
            return a_df

        def got_tags(tags):
            for t in tags:
                for file in file_list:
                    df.addCallback(apply_tag, file, t)

            df.addCallback(outer_df.callback)

        def get_tags(val):
            ta = TagAggregator(self, self.model, tag_names, True)
            ta_df = ta.go(got_tags)
            return ta_df

        if len(tag_names) == 0:
            outer_df.callback(None)
        else:
            df = defer.Deferred()
            df.addCallback(get_tags)
            df.callback(None)

        return outer_df


    def add_plugin(self, callback, name, module_name):
        outer_df = defer.Deferred()
        outer_df.addCallback(callback)

        df = defer.Deferred()

        def got_plugin(plugin):
            if plugin is None:
                # If the plugin doesn't exist, create it and return it to the callback
                plugin = Plugin(name, module_name)

                def save_plugin(val):
                    s_df = self.model.save(plugin)
                    return s_df

                def done(val):
                    outer_df.callback(plugin)

                df.addCallback(save_plugin)
                df.addCallback(done)

                df.callback(None)
            else:
                # If it does exist, return None to the callback.
                outer_df.callback(None)

        self.model.get_plugin(got_plugin, name=name, module_name=module_name)

        return outer_df


    def find_files_by_tags(self, callback, tag_names, user_name=None):
        outer_df = defer.Deferred()
        outer_df.addCallback(callback)

        def got_files(files):
            outer_df.callback(files)

        def got_tags(tags):
            if len(tags) != len(tag_names):
                # if we got back fewer tags than we searched for,
                # it means that not all tags exist. thus no file will have all those tags
                # thus we can stop looking
                outer_df.callback([])
                return None
            else:
                fa = FileAggregator(self, self.model, tags, user_name=user_name)
                fa_df = fa.go(got_files)
                return fa_df

        def get_tags():
            ta = TagAggregator(self, self.model, tag_names, False)
            ta_df = ta.go(got_tags)
            return ta_df

        # start searching...
        get_tags()

        return outer_df

