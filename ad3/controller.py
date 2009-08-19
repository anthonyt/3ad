import sys
import os
from numpy import array, concatenate, divide, mean
from ad3.models.dht import AudioFile, Plugin, PluginOutput, Tag
from twisted.internet import defer
from functools import partial
from sets import Set

from logs import logger

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

    def go(self):
        def done(val):
            return self.tag_objs

        def handle_tag(tag, name):
            # only create the missing tag if force_creation is enabled
            if tag is None and self.force_creation:
                tag = Tag(name)
                save_df = self.model.save(tag)
            else:
                save_df = None

            if tag is not None:
                self.tag_objs.append(tag)

            return save_df

        dfs = []
        for name in self.tag_names:
            t_df = self.model.get_tag(name)
            t_df.addCallback(handle_tag, name)
            dfs.append(t_df)

        list_df = defer.DeferredList(dfs)
        list_df.addCallback(done)
        return list_df

class FileAggregator(object):
    def __init__(self, controller, model, tag_list, user_name=None):
        self.controller = controller
        self.model = model
        self.tag_list = tag_list #list of tag objects
        self.user_name = user_name

        self.num_got_files = 0
        self.file_lists = {}

    def go(self):
        def got_all_files(val):
            # find the Set of files such that every file belongs to every tag
            files = None
            for tag_name in self.file_lists:
                if files is None:
                    logger.debug(self.file_lists[tag_name])
                    files = Set(self.file_lists[tag_name])
                else:
                    files = files.intersection(self.file_lists[tag_name])

            return list(files)

        def got_files(files, tag_name):
            if files is not None:
                self.file_lists[tag_name].extend(files)

        dfs = []
        for tag in self.tag_list:
            self.file_lists[tag.name] = []

            df_t = self.model.get_audio_files(tag=tag, user_name=self.user_name)
            df_t.addCallback(got_files, tag.name)
            dfs.append(df_t)

            df_g = self.model.get_audio_files(guessed_tag=tag, user_name=self.user_name)
            df_g.addCallback(got_files, tag.name)
            dfs.append(df_g)

        list_df = defer.DeferredList(dfs)
        list_df.addCallback(got_all_files)

        return list_df


class Controller(object):

    def __init__(self, data_model, learning_algorithm):
        self.model = data_model
        self.mine = learning_algorithm

    def initialize_storage(self, callback):
        self.model.initialize_storage(callback)

    def update_tag_vectors(self, tag_name = None):
        def got_vector(vector, tag):
            tag.vector = vector
            logger.debug("-> Saving vector for %r", tag)
            s_df = self.model.save(tag)
            return s_df

        # Update the vector for every tag, based on the new output
        def got_tags(tags):
            dfs = []
            for tag in tags:
                logger.debug("-> Fetching vector for %r", tag)
                cb = partial(got_vector, tag)
                t_df = self.mine.calculate_tag_vector(tag)
                t_df.addCallback(got_vector, tag)

            list_df = defer.DeferredList(dfs)
            return list_df


        df = self.model.get_tags(name=tag_name)
        df.addCallback(got_tags)
        return df


    def create_vectors(self, file, plugin_name=None):
        def update_file_vector(val):
            # this deferred will pass the calculated vector onto the next callback
            df = self.mine.calculate_file_vector(file)
            return df

        df = self.model.update_vector(file)
        df.addCallback(update_file_vector)
        return df



    def guess_tags(self, audio_file=None, user_name=None):
        # We use a list to allow modification of the tags variable
        # from within the functions defined below.
        scoped_tags = [0]

        def got_files(files):
            tags = scoped_tags[0]

            dfs = []
            for file in files:
                for tag in tags:
                    if self.mine.does_tag_match(file, tag):
                        logger.debug("-> GENERATED: %r %r", file, tag)
                        df = self.model.guess_tag_for_file(file, tag)
                        dfs.append(df)
            list_df = defer.DeferredList(dfs)
            return list_df

        def got_tags(tags):
            scoped_tags[0] = tags

            # take care of fetching the tag and audio file objects...
            if audio_file is None:
                f_df = self.model.get_audio_files(user_name=user_name)
            else:
                f_df = defer.Deferred()
                f_df.callback([audio_file])

            df.addCallback(got_files)
            return df

        def get_tags(val):
            df = self.model.get_tags()
            return df

        df = self.model.remove_guessed_tags()
        df.addCallback(get_tags)
        df.addCallback(got_tags)
        df.addCallback(got_files)
        return df

    def add_files(self, file_names, user_name, tags=None):
        result_tuples = {}

        def done(val):
            logger.debug("Calling back outer_df with %r", result_tuples)
            return result_tuples

        if tags is None:
            tags = []

        def got_file(file, file_name):
            inner_df = defer.Deferred()

            if file is not None:
                # file already exists
                result_tuples[file_name] = (file, False)
            else:
                # make a new file!
                file = AudioFile(file_name, user_name=user_name)
                result_tuples[file_name] = (file, True)

                def save_file(val):
                    logger.debug("--> Saving %r", file_name)
                    save_df = self.model.save(file)
                    return save_df

                def apply_vector(vector):
                    logger.debug("--> Applying vector to %r %r", file_name, vector)
                    file.vector = vector
                    return None

                inner_df.addCallback(self.create_vectors) # passes the vector to the next callback
                inner_df.addCallback(apply_vector)
                inner_df.addCallback(save_file)

                # After the file has been saved, apply the tags to it!
                # TODO: we shouldn't get_tags for each file individually. Do it once, before saving any files.
                if tags:
                    def got_tags(tags):
                        # Make sure that each apply_tag_to_file call does not overlap
                        # FIXME: Not sure if we need this now that the network
                        #        is tolerant of packet loss.
                        def apply(value, file, tag):
                            logger.debug("Attempting to apply: %r to %r ", tag, file)
                            tag_df = self.model.apply_tag_to_file(file, tag)
                            return tag_df

                        df = defer.Deferred()
                        for t in tags:
                            df.addCallback(apply, file, t)
                        df.callback(None)
                        return df

                    def get_tags(val):
                        ta = TagAggregator(self, self.model, tags, True)
                        ta_df = ta.go()
                        return ta_df

                    inner_df.addCallback(get_tags)
                    inner_df.addCallback(got_tags)

                # Pass "file" to our first callback
                inner_df.callback(file)

                # inner_df will 'callback', as far as the calling function is
                # concerned, either after the file is saved, or after all tags
                # have been applied, depending on the presence of a tags list
                return inner_df

        dfs = []
        for file_name in file_names:
            logger.debug("Getting audio file...")
            df = self.model.get_audio_file(file_name=file_name, user_name=user_name)
            df.addCallback(got_file, file_name)
            dfs.append(df)

        # All got_file calls will return a deferred. Because of this,
        # list_df.callback() isn't called until all got_file calls are
        # finished with their business.
        list_df = defer.DeferredList(dfs)
        list_df.addCallback(done)
        return list_df


    def add_file(self, file_name, user_name=None, tags=None):
        def done(result):
            return result[file_name]

        df = self.add_files([file_name], user_name, tags)
        df.addCallback(done)
        return df


    def tag_files(self, file_list, tag_names=[]):
        def apply_tag(val, file, tag):
            a_df = self.model.apply_tag_to_file(file, tag)
            return a_df

        def got_tags(tags):
            inner_df = defer.Deferred()
            for t in tags:
                for file in file_list:
                    inner_df.addCallback(apply_tag, file, t)
            inner_df.callback(None)
            return inner_df

        def get_tags(val):
            ta = TagAggregator(self, self.model, tag_names, True)
            ta_df = ta.go()
            return ta_df

        outer_df = defer.Deferred()
        if len(tag_names) == 0:
            outer_df.callback(None)
        else:
            df = defer.Deferred()
            df.addCallback(get_tags)
            df.addCallback(got_tags)
            df.addCallback(outer_df.callback)
            df.callback(None)

        return outer_df


    def add_plugin(self, name, module_name):
        outer_df = defer.Deferred()

        def got_plugin(plugin):
            if plugin is None:
                # If the plugin doesn't exist, create it and return it to the callback
                plugin = Plugin(name, module_name)

                def done(val):
                    outer_df.callback(plugin)

                df = self.model.save(plugin)
                df.addCallback(done)
            else:
                # If it does exist, return None to the callback.
                outer_df.callback(None)

        df = self.model.get_plugin(name=name, module_name=module_name)
        df.addCallback(got_plugin)

        return outer_df


    def find_files_by_tags(self, tag_names, user_name=None):
        def got_tags(tags):
            if len(tags) != len(tag_names):
                # if we got back fewer tags than we searched for,
                # it means that not all tags exist. thus no file will have all those tags
                # thus we can stop looking
                return []
            else:
                # fa_df will eventually return a list of files.
                fa = FileAggregator(self, self.model, tags, user_name=user_name)
                fa_df = fa.go()
                return fa_df

        # start searching...
        ta = TagAggregator(self, self.model, tag_names, False)
        df = ta.go()
        df.addCallback(got_tags)
        return df

