from sqlalchemy import create_engine, func
from sqlalchemy import Table, Column, Integer, String, PickleType, MetaData, ForeignKey
from sqlalchemy.orm import mapper
from sqlalchemy.orm import relation
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from numpy import mean, array, dot, sqrt

import ad3.models.abstract

class Database(object):
    __shared_state = {'session': None}

    def createTables(self):
        return self.metadata.create_all(self.engine)

    def dropTables(self):
        return self.metadata.drop_all(self.engine)

    def add(self, object):
        return self.session.add(object)

    def delete(self, object):
        return self.session.delete(object)

    def query(self, *entities, **kwargs):
        return self.session.query(*entities, **kwargs)

    def commit(self):
        return self.session.commit()

    def __create_metadata(self):
        self.metadata = MetaData()

        self.plugins_table = Table(
            'plugins',
            self.metadata,
            Column('id', Integer, primary_key=True),
            Column('name', String(255)),
            Column('module_name', String(255))
        )

        self.output_table = Table(
            'output',
            self.metadata,
            Column('id', Integer, primary_key=True),
            Column('plugin_id', Integer, ForeignKey('plugins.id')),
            Column('audiofile_id', Integer, ForeignKey('audiofiles.id')),
            Column('vector', PickleType)
        )

        self.audiofiles_table = Table(
            'audiofiles',
            self.metadata,
            Column('id', Integer, primary_key=True),
            Column('file_name', String(255)),
            Column('vector', PickleType)
        )

        self.tags_table = Table(
            'tags',
            self.metadata,
            Column('id', Integer, primary_key=True),
            Column('name', String(255)),
            Column('vector', PickleType)
        )

        self.audiofiles_tags = Table(
            'audiofiles_tags',
            self.metadata,
            Column('audiofile_id', Integer, ForeignKey('audiofiles.id')),
            Column('tag_id', Integer, ForeignKey('tags.id'))
        )

        self.audiofiles_generatedtags = Table(
            'audiofiles_generatedtags',
            self.metadata,
            Column('audiofile_id', Integer, ForeignKey('audiofiles.id')),
            Column('tag_id', Integer, ForeignKey('tags.id'))
        )


    def __create_mappings(self):
        mapper(
            Plugin,
            self.plugins_table
        )

        mapper(
            PluginOutput,
            self.output_table,
            properties = {
                'plugin': relation(Plugin, backref='outputs'),
                'file': relation(AudioFile, backref='outputs')
            }
        )

        mapper(
            AudioFile,
            self.audiofiles_table,
            properties = {
                'tags': relation(Tag, secondary=self.audiofiles_tags),
                'generated_tags': relation(Tag, secondary=self.audiofiles_generatedtags)
            }
        )

        mapper(
            Tag,
            self.tags_table,
            properties = {
                'files': relation(AudioFile, secondary=self.audiofiles_tags),
                'detected_files': relation(AudioFile, secondary=self.audiofiles_generatedtags)
            }
        )

    def __init__(self):
        self.__dict__ = self.__shared_state

        if self.session == None:
            self.engine = create_engine('mysql://root:@localhost/3ad', echo=False)

            self.__create_metadata();
            self.__create_mappings();

            Session = sessionmaker(bind=self.engine, autoflush=True)
            self.session = Session()


class Saveable(object):
    def save(self):
        if self.id is None:
            db.add(self)

class Plugin(Saveable, ad3.models.abstract.Plugin):
    def create_vector(self, audiofile):
        return PluginOutput(self.module.createVector(audiofile.file_name), self, audiofile)

class AudioFile(Saveable, ad3.models.abstract.AudioFile):
    pass

class Tag(Saveable, ad3.models.abstract.Tag):
    pass

class PluginOutput(Saveable, ad3.models.abstract.PluginOutput):
    pass


# Global framework variables
db = Database()

def get_tags(name = None):
    """ Return a list of Tag objects. By default returns all tags.

    @param name: return only tags with tag.name matching provided name
    @type  name: unicode
    """
    query = db.query(Tag)
    if name is not None:
        query = query.filter_by(name = name)
    return query.all()

def get_tag(name):
    """ Returns a single Tag object with the provided name, if one exists in the data store.

    @param name: the name of the tag object to return
    @type  name: unicode
    """
    query = db.query(Tag).filter_by(name = name)
    try:
        tag = query.one()
    except NoResultFound:
        tag = Tag(name)
        tag.save()

    return tag

def initialize_storage():
    """ Initializes an empty storage environment.

    For a database, this might mean to (re)create all tables.
    """
    # drop the old tables
    db.dropTables()
    # create the fresh tables
    db.createTables()

def get_plugins(name = None, module_name = None):
    """ Return a list of Plugin objects. By default returns all plugins.

    @param name: if provided, returns only plugins with a matching name
    @type  name: unicode

    @param module_name: if provided, returns only plugins with a matching module_name
    @type  module_name: unicode
    """
    query = db.query(Plugin).order_by(Plugin.name)
    if name is not None:
        query = query.filter_by(name = name)

    if module_name is not None:
        query = query.filter_by(module_name = module_name)

    return query.all()

def get_audio_files(file_name=None, tag_names=None, include_guessed=False):
    """ Return a list of AudioFile objects. By default returns all audio files.

    @param file_name: if provided, returns only files with a matching file name
    @type  file_name: unicode

    @param tag_names: if provided, returns only files with at least one of the provided tags
    @type  tag_names: list of unicode objects

    @param include_guessed: if provided, when looking for matching tags, includes generated_tags in the search
    @type  include_guessed: bool
    """
    query = db.query(AudioFile)
    if file_name is not None:
        query = query.filter_by(file_name=file_name)

    if tag_names is not None:
        query = query.join(AudioFile.tags)\
                     .filter(Tag.name.in_(tag_names))\
                     .group_by(AudioFile.id)\
                     .having(func.count(AudioFile.id) == len(tag_names))
        if include_guessed:
            # TODO: Include support for the include_guessed parameter!!
            # this is pretty integral to the functioning of the app.
            pass

    return query.all()

def get_audio_file(file_name):
    """ Return an AudioFile object. If no existing object is found, returns None.

    @param file_name: the file name of the audio file
    @type  file_name: unicode
    """
    try:
        query = db.query(AudioFile).filter_by(file_name=file_name)
        return query.one()
    except NoResultFound:
        return None

def save(obj):
    """ Save an object to permanent storage.

    @param obj: the object to save
    @type  obj: Saveable
    """
    obj.save()
    db.commit()

def update_vector(plugin, audio_file):
    """ Create or Replace the current PluginOutput object for the
    provided plugin/audio file pair. Saves the PluginObject to storage.

    @param plugin: the plugin object to use
    @type  plugin: Plugin

    @param audio_file: the audio file to run the plugin on
    @type  audio_file: AudioFile
    """
    for old_output in db.query(PluginOutput).filter_by(plugin=plugin,file=audio_file):
        # there should really only be one output with the same file/plugin combo
        db.delete(old_output)
    PO = plugin.create_vector(audio_file)
    save(PO)
    return PO

