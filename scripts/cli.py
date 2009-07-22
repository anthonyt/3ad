#!/usr/bin/env python
import os
import sys
import time
import hashlib
import cPickle
import tty
import termios
import keyword
import __builtin__

from time import sleep
from functools import partial
from IPython.completer import Completer

from twisted.internet import selectreactor
from twisted.internet import reactor
from twisted.internet import defer
from twisted.internet import stdio
from twisted.conch.insults.insults import ServerProtocol
from twisted.conch.manhole import Manhole, ColoredManhole, ManholeInterpreter

from entangled.kademlia.datastore import SQLiteDataStore

# ensure the main ad3 module is on the path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
        sys.path.append(parent_dir)

import ad3
import ad3.models
import ad3.models.dht
from ad3.models.dht import AudioFile, Plugin, Tag, PluginOutput
from ad3.learning import *
from ad3.learning.euclid import Euclidean
from ad3.learning.gauss import Gaussian
from ad3.learning.svm import SVM
from ad3.controller import Controller

import logging
from entangled.kademlia import logs as kademlia_logs
from ad3 import logs as ad3_logs

defer.setDebugging(True)

class ConsoleManholeInterpreter(ManholeInterpreter):
    def displayhook(self, obj):
        ManholeInterpreter.displayhook(self, obj)
        if isinstance(obj, defer.Deferred):
            # If we need custom handling for displaying deferreds, add it here
            pass

    def runcode(self, *a, **kw):
        ManholeInterpreter.runcode(self, *a, **kw)


class ConsoleManhole(ColoredManhole):
    """
    Adapted from this awesome mailing list entry:
    http://twistedmatrix.com/pipermail/twisted-python/2009-January/019003.html
    """
    def __init__(self, namespace=None):
        ColoredManhole.__init__(self, namespace)
        self.completer = Completer(namespace=self.namespace)
        self.completeState = 0
        self.lastTabbed = ''
        self.lastSuggested = ''
        self.sem = defer.DeferredLock()
        self.enabled = True

    def connectionLost(self, reason):
        ColoredManhole.connectionLost(self, reason)
        reactor.stop()
        print ""

    def connectionMade(self):
        ColoredManhole.connectionMade(self)
        self.interpreter = ConsoleManholeInterpreter(self, self.namespace)

    def disableInput(self):
        #print "Disabling\r"
        self.enabled = False

    def enableInput(self):
        #print "Enabling\r"
        self.enabled = True

    def lineReceived(self, line):
        #print "\r"
        def fn():
            df = defer.Deferred()
            def fn2():
                #print "Running lineReceived\r"
                a = ColoredManhole.lineReceived(self, line)
                df.callback(a)

            reactor.callLater(0, fn2)
            return df

        self.sem.run(fn)

    def keystrokeReceived(self, keyID, modifier):
        if keyID in self.keyHandlers or self.enabled:
            ColoredManhole.keystrokeReceived(self, keyID, modifier)
        else:
            #print "ignoring\r"
            pass

    def handle_TAB(self):
        s = "".join(self.lineBuffer)

        if s == self.lastTabbed + self.lastSuggested:
            # If the user has typed nothing since the last tab,
            # erase the last suggestion
            for i in range(0, len(self.lastSuggested)):
                self.handle_BACKSPACE()

            s = s[:len(self.lastTabbed)]
        else:
            # if the user has typed something since the last tab,
            # keep the current text and reset the tab counter
            self.completeState = 0
            self.lastTabbed = s

        # When matching, match only against the last space-separated word.
        s = s.strip()
        try:
            s = s[s.rindex(' '):].strip()
        except ValueError:
            pass

        c = self.completer.complete(s, self.completeState)

        if c is None:
            c = ''
            self.completeState = 0
        else:
            self.completeState += 1
            c = c[len(s):]

        self.lastSuggested = c

        for ch in c:
            self.lineBuffer[self.lineBufferIndex:self.lineBufferIndex+1] = [ch]
            self.lineBufferIndex += len(ch)
            self.terminal.write(ch)

# DECORATORS
def cont(fn):
    def f(*a, **kw):
        if not isinstance(p.terminalProtocol.namespace['controller'], Controller):
            print "Please connect first\r"
            print "see help(connect) for details\r"
            return None
        else:
            return fn(*a, **kw)
    f.__doc__ = fn.__doc__
    return f

def sync(fn):
    def s(*a, **kw):
        def f(v):
            p.terminalProtocol.namespace['_result'] = v
            p.terminalProtocol.enableInput()
            return v
        p.terminalProtocol.disableInput()
        try:
            df = fn(*a, **kw)
            if isinstance(df, defer.Deferred):
                df.addBoth(f)
            else:
                f(df)
            return df
        except Exception, e:
            p.terminalProtocol.enableInput()
            raise e
    s.__doc__ = fn.__doc__
    return s

def connect(udpPort=None, userName=None, knownNodes=None, dbFile=':memory:', logFile='3ad.log'):
    """
    udpPort: int
    userName: str
    knownNodes: list of tuples in form [('127.0.0.1', 4000)]
    dbFile: path to sqlite database file

    udpPort will be read from first command line argument, if None
    userName will be read from second command line argument, if None
    """

    if udpPort is None:
        udpPort = int(sys.argv[1])
    if userName is None:
        userName = sys.argv[2]
    if knownNodes is None:
        knownNodes = [('127.0.0.1', 4000)]

    # Set up model with its network node
    model = ad3.models.dht
    dataStore = SQLiteDataStore(dbFile=dbFile)
    node = ad3.models.dht.MyNode(udpPort=udpPort, dataStore=dataStore)

    formatter = logging.Formatter("%(name)s: %(levelname)s %(created)f %(filename)s:%(lineno)d (in %(funcName)s): %(message)s")
    handler = logging.FileHandler(logFile)
    handler.setFormatter(formatter)
    # set up the kademlia logs
    kademlia_logs.addHandler(handler)
    kademlia_logs.logger.setLevel(logging.DEBUG)
    # set up the ad3 logs
    ad3_logs.addHandler(handler)
    ad3_logs.logger.setLevel(logging.DEBUG)

    #print "->", "joining network..."
    node.joinNetwork(knownNodes)
    #print "->", "joined network..."
    # create a newtwork handler using the network node
    nh = ad3.models.dht.NetworkHandler(node)
    # Set the network handler for the model.
    ad3.models.dht.set_network_handler(nh)

    # Set up the classifier
    gaussian = Gaussian(model, 100)

    # Set up the controller
    controller = Controller(model, gaussian)

    p.terminalProtocol.namespace['controller'] = controller
    p.terminalProtocol.namespace['userName'] = userName
    p.terminalProtocol.namespace['node'] = controller.model._network_handler.node

    return controller

"""
    need to:
        add file (path) -> file
        add file (path, tag) -> file
        add file (path, tag list) -> file

        add files (path list) -> file list
        add files (path list, tag) -> file list
        add files (path list, tag list) -> file list

        list files -> file list
        list files (path fragment) -> file list
        list files (tag name) -> file list

        list tags -> tag list
        list tags (tag fragment) -> tag list

        print file (file) -> void
        print files (file list) -> void

        update tag vectors -> void
        update guessed tags -> void

        save to database (filename) -> void
        retrieve from database (filename) -> void
"""

def to_tag_list(tags):
    # Make sure tags is a list of tag names.
    if tags is not None:
        if not isinstance(tags, list):
            tags = [tags]
        def f(t):
            if isinstance(t, Tag):
                return t.name
            else:
                return t
        tags = map(f, tags)
    return tags

@sync
@cont
def store_a_bunch_of_data(offset=0, num=1000):
    n = p.terminalProtocol.namespace
    node = n['controller'].model._network_handler.node

    for i in range(0, num):
        key = value = str(offset + i)
        df = node.iterativeStore(key, value)

    return None

@sync
@cont
def read_a_bunch_of_data(offset=0, num=1000):
    n = p.terminalProtocol.namespace
    node = n['controller'].model._network_handler.node
    ds = node._dataStore

    count_in = 0
    count_good = 0
    for i in range(0, num):
        key = str(offset + i)
        if key in ds:
            count_in += 1
            if ds[key] == key:
                count_good += 1


    return dict(cin=count_in, cgd=count_good)

@sync
@cont
def add_plugin(module_name, name=None):
    """
    @param module_name: the module name of the plugin
    @type  module_name: str or unicode

    @param name: the name of this plugin
    @type  name: str or unicode
    """
    if name is None:
        name = module_name

    n = p.terminalProtocol.namespace
    def f(v):
        return v
    df = n['controller'].add_plugin(f, name, module_name)
    return df

@sync
@cont
def add_file(path, tags=None):
    """
    @param path: path to audio file (wav, aif, mp3)
    @type  path: str or unicode

    @param tags: list of tags to apply to the file
    @type  tags: str, Tag object, or list of str/Tag objects
    """
    tags = to_tag_list(tags)

    n = p.terminalProtocol.namespace
    def f(v):
        return v
    df = n['controller'].add_file(f, path, user_name=n['userName'], tags=tags)
    return df

@sync
@cont
def add_files(paths, tags=None):
    """
    @param paths: list of paths to audio files (wav, aif, mp3)
    @type  paths: list of str or unicode

    @param tags: list of tags to apply to the file
    @type  tags: str, Tag object, or list of str/Tag objects
    """
    tags = to_tag_list(tags)

    outer_df = defer.Deferred()
    def f(v):
        # parse the results from the wierd format that the controller returns.
        results = [v[k][0] for k in v if v[k][1]]
        outer_df.callback(results)

    n = p.terminalProtocol.namespace
    df = n['controller'].add_files(paths, user_name=n['userName'], tags=tags)
    df.addBoth(f)

    return outer_df

@cont
def get_files(fileName=None, userName=None, tags=None, guessedTags=None, pluginOutput=None):
    """
    @param fileName: if provided, returns only files with a matching file name
    @type  fileName: unicode

    @param userName: if provided, returns only files with a matching user name
    @type  userName: unicode

    @param tags: if provided, returns only files manually tagged with the provided tag
    @type  tags: Tag object

    @param guessedTags: if provided, returns only files automatically tagged with the provided tag
    @type  guessedTags: Tag object

    @param pluginOutput: if provided, returns only the file associated with this output
    @type  pluginOutput: PluginOutput object
    """
    n = p.terminalProtocol.namespace
    df = defer.Deferred()

    if userName is None:
        userName = n['userName']
    if userName is '':
        username = None

    def f(v):
        df.callback(v)
    n['controller'].model.get_audio_files(f, file_name=fileName, user_name=userName, tag=tags, guessed_tag=guessedTags, plugin_output=pluginOutput)
    return df

@cont
def get_tags(name=None, audioFile=None, guessedAudioFile=None):
    """
    @param name: return only tags with tag.name matching provided name
    @type  name: unicode

    @param audioFile: return only tags that have been applied to this audio file
    @type  audioFile: AudioFile object

    @param guessedAudioFile: return only tags that have been guessed for this audio file
    @type  guessedAudioFile: AudioFile object
    """
    n = p.terminalProtocol.namespace
    df = defer.Deferred()

    def f(v):
        df.callback(v)
    n['controller'].model.get_tags(f, name=name, audio_file=audioFile, guessed_file=guessedAudioFile)
    return df

@cont
def print_file(file):
    """
    @param file: the file to be printed
    @type  file: AudioFile object
    """
    outer_df = defer.Deferred()
    res = dict()

    def f(tags):
        res['tags'] = tags

    def g(tags):
        res['guessed_tags'] = tags

    def pr(v):
        print "\r"
        print file, "\r"
        print res, "\r"
        return v


    df_f = get_tags(audioFile=file)
    df_f.addCallback(f)
    df_g = get_tags(guessedAudioFile=file)
    df_g.addCallback(g)
    df_l = defer.DeferredList([df_f, df_g])
    df_l.addCallback(pr)
    df_l.addCallback(outer_df.callback)
    return outer_df


@sync
@cont
def print_files(files):
    """
    @param files: the files to be printed
    @type  files: list of AudioFile objects
    """
    df_lock = defer.DeferredLock()
    df_list = [df_lock.run(print_file, file) for file in files]
    dl = defer.DeferredList(df_list)
    return dl

@sync
@cont
def update_tag_vectors():
    """
    Update the vectors for all tags based on the vectors for all files with each tag.
    """
    n = p.terminalProtocol.namespace
    df = defer.Deferred()

    def f(v):
        df.callback(v)
    n['controller'].update_tag_vectors(f)
    return df

@sync
@cont
def update_file_vector(file):
    """
    @param file: the file for which we will update the vectors
    @type  file: AudioFile object
    """
    n = p.terminalProtocol.namespace
    df = n['controller'].create_vectors(file)
    return df

@sync
@cont
def update_predictions():
    """
    Update all predicted tags.
    """
    n = p.terminalProtocol.namespace
    df = defer.Deferred()

    def f(v):
        df.callback(v)
    n['controller'].guess_tags(f, user_name=n['userName'])
    return df

@cont
def create_db_snapshot(outFile):
    """
    @param outFile: the path to save the database to
    @type  outFile: str

    thanks to: http://osdir.com/ml/python.db.pysqlite.user/2006-01/msg00022.html
    """
    n = p.terminalProtocol.namespace
    ds = n['controller'].model._network_handler.node._dataStore
    cur = ds._cursor
    con = ds._db
    columns = [
        'key',
        'value',
        'lastPublished',
        'originallyPublished',
        'originalPublisherID'
    ]
    col_str = ', '.join(columns)

    # Detatch the current backup database, if there is one
    try:
        cur.execute('DETACH backup')
    except Exception, e:
        pass
    finally:
        con.commit()

    # erase the old db file, if it exists
    if os.path.exists(outFile):
        os.remove(outFile)

    # Create a new DB file, copying over the current state.
    cur.execute('ATTACH \'%s\' AS backup' % outFile)
    cur.execute('CREATE TABLE backup.data(%s)' % col_str)
    cur.execute('INSERT INTO backup.data(%s) SELECT %s FROM data' % (col_str, col_str))
    con.commit()

cmds = dict(
    test_conn = partial(connect, 4000, 'anthony', dbFile='bob.sqlite'),
    sync = sync,
    add_plugin=add_plugin,
    add_file=add_file,
    add_files=add_files,
    get_files=sync(get_files),
    get_tags=sync(get_tags),
    print_file=sync(print_file),
    print_files=print_files,
    update_tag_vectors=update_tag_vectors,
    update_file_vector=update_file_vector,
    update_predictions=update_predictions,
    create_db_snapshot=create_db_snapshot,
    store_a_bunch_of_data=store_a_bunch_of_data,
    read_a_bunch_of_data=read_a_bunch_of_data
)

namespace = dict(
    commands = cmds,
    __name__ = '__console__',
    __doc__ = None,
    _result = None,
    connect = connect,
    controller = None
)

for cmd in cmds:
    namespace[cmd] = cmds[cmd]

fd = sys.__stdin__.fileno()
oldSettings = termios.tcgetattr(fd)
tty.setraw(fd)
try:
    p = ServerProtocol(ConsoleManhole, namespace=namespace)
    stdio.StandardIO(p)
    reactor.run()
finally:
    termios.tcsetattr(fd, termios.TCSANOW, oldSettings)
    os.write(fd, "\r\x1bc\r")

