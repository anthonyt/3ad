from sqlalchemy import create_engine
from sqlalchemy import Table, Column, Integer, String, PickleType, MetaData, ForeignKey
from sqlalchemy.orm import mapper
from sqlalchemy.orm import relation
from sqlalchemy.orm import sessionmaker


engine = create_engine('mysql://root:@localhost/3ad', echo=True)

metadata = MetaData()

plugins_table = Table(
	'plugins',
	metadata,
	Column('id', Integer, primary_key=True),
	Column('name', String(255)),
	Column('modulename', String(255))
)

output_table = Table(
	'output',
	metadata,
	Column('id', Integer, primary_key=True),
	Column('plugin_id', Integer, ForeignKey('plugins.id')),
	Column('audiofile_id', Integer, ForeignKey('audiofiles.id')),
	Column('vector', PickleType)
)

audiofiles_table = Table(
	'audiofiles',
	metadata,
	Column('id', Integer, primary_key=True),
	Column('filename', String(255))
)

tags_table = Table(
	'tags',
	metadata,
	Column('id', Integer, primary_key=True),
	Column('name', String(255))
)

audiofiles_tags = Table(
	'audiofiles_tags',
	metadata,
	Column('audiofile_id', Integer, ForeignKey('audiofiles.id')),
	Column('tag_id', Integer, ForeignKey('tags.id'))
)



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


mapper(
	Plugin,
	plugins_table
)

mapper(
	PluginOutput,
	output_table,
	properties = {
		'plugin': relation(Plugin, backref='outputs'),
		'file': relation(AudioFile, backref='outputs')
	}
)

mapper(
	AudioFile,
	audiofiles_table,
	properties = {
		'tags': relation(Tag, secondary=audiofiles_tags)
	}
)

mapper(
	Tag,
	tags_table,
	properties = {
		'files': relation(AudioFile, secondary=audiofiles_tags)
	}
)

Session = sessionmaker(bind=engine, autoflush=True, transactional=True)
session = Session()


