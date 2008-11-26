from sqlalchemy import create_engine
from sqlalchemy import Table, Column, Integer, String, PickleType, MetaData, ForeignKey
from sqlalchemy.orm import mapper
from sqlalchemy.orm import relation
from sqlalchemy.orm import sessionmaker


class Plugin(object):
	def __init__(self, name, modulename):
		self.name = name
		self.modulename = modulename
		self.module = __import__(modulename)

	def __repr__(self):
		return "<Plugin('%s','%s', '%s')>" % (self.name, self.modulename)

	def createData(inputFile):
		return self.module.createData(inputFile)


class PluginOutput(object):
	def __init__(self, vector):
		self.vector = vector

	def __repr__(self):
		return "<PluginOutput('%s')>" % (self.vector)


class AudioFile(object):
	def __init__(self, filename):
		self.filename = filename

	def __repr__(self):
		return "<AudioFile('%s')>" % (self.filename)


class Tag(object):
	def __init__(self, name):
		self.name = name

	def __repr__(self):
		return "<Tag('%s')>" % (self.name)


class Database(object):
	__shared_state = {'session': None}

	def create_metadata(self):
		metadata = MetaData()

		self.plugins_table = Table(
			'plugins',
			metadata,
			Column('id', Integer, primary_key=True),
			Column('name', String(255)),
			Column('modulename', String(255))
		)

		self.output_table = Table(
			'output',
			metadata,
			Column('id', Integer, primary_key=True),
			Column('plugin_id', Integer, ForeignKey('plugins.id')),
			Column('audiofile_id', Integer, ForeignKey('audiofiles.id')),
			Column('vector', PickleType)
		)

		self.audiofiles_table = Table(
			'audiofiles',
			metadata,
			Column('id', Integer, primary_key=True),
			Column('filename', String(255))
		)

		self.tags_table = Table(
			'tags',
			metadata,
			Column('id', Integer, primary_key=True),
			Column('name', String(255))
		)

		self.audiofiles_tags = Table(
			'audiofiles_tags',
			metadata,
			Column('audiofile_id', Integer, ForeignKey('audiofiles.id')),
			Column('tag_id', Integer, ForeignKey('tags.id'))
		)


	def create_mappings(self):
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
				'tags': relation(Tag, secondary=self.audiofiles_tags)
			}
		)

		mapper(
			Tag,
			self.tags_table,
			properties = {
				'files': relation(AudioFile, secondary=self.audiofiles_tags)
			}
		)

	def __init__(self):
		self.__dict__ = self.__shared_state

		if self.session == None:
			self.engine = create_engine('mysql://root:@localhost/3ad', echo=True)

			self.create_metadata();
			self.create_mappings();

			Session = sessionmaker(bind=self.engine, autoflush=True, transactional=True)
			self.session = Session()

