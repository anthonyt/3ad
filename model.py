from sqlalchemy import create_engine
from sqlalchemy import Table, Column, Integer, String, PickleType, MetaData, ForeignKey
from sqlalchemy.orm import mapper
from sqlalchemy.orm import relation
from sqlalchemy.orm import sessionmaker


class Plugin(object):
	def __init__(self, name, modulename):
		self.name = name
		self.modulename = modulename
		self.__setupModule()

	def __setupModule(self):
		if not hasattr(self, 'module'):
			mod = __import__(self.modulename)
			components = self.modulename.split('.')
			for comp in components[1:]:
				mod = getattr(mod, comp)
			self.module = mod

	def __repr__(self):
		return "<Plugin('%s','%s')>" % (self.name, self.modulename)

	def createVector(self, audiofile):
		self.__setupModule()
		return PluginOutput(self.module.createVector(audiofile.filename), self, audiofile)


class PluginOutput(object):
	def __init__(self, vector, plugin, audiofile):
		self.vector = vector
		self.plugin = plugin
		self.file = audiofile

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

	def createTables(self):
		return self.metadata.create_all(self.engine)

	def saveObject(self, object):
		return self.session.save(object)

	def __create_metadata(self):
		self.metadata = MetaData()

		self.plugins_table = Table(
			'plugins',
			self.metadata,
			Column('id', Integer, primary_key=True),
			Column('name', String(255)),
			Column('modulename', String(255))
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
			Column('filename', String(255))
		)

		self.tags_table = Table(
			'tags',
			self.metadata,
			Column('id', Integer, primary_key=True),
			Column('name', String(255))
		)

		self.audiofiles_tags = Table(
			'audiofiles_tags',
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

			self.__create_metadata();
			self.__create_mappings();

			Session = sessionmaker(bind=self.engine, autoflush=True, transactional=True)
			self.session = Session()

