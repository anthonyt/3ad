#!/usr/bin/env python2.5

import os
import sys
import time
import hashlib
import cPickle
import tty
import termios
import keyword
import __builtin__
import random

from functools import partial
from copy import copy
from IPython.completer import Completer

from twisted.internet import selectreactor
from twisted.internet import reactor
from twisted.internet import defer
from twisted.internet import stdio
from twisted.conch.insults.insults import ServerProtocol
from twisted.conch.manhole import Manhole, ColoredManhole, ManholeInterpreter

import entangled
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
from ad3.controller import Controller, TagAggregator, FileAggregator

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

def connect(udpPort=None, tcpPort=None, userName=None, knownNodes=None, dbFile=':memory:', logFile='3ad.log'):
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
    if tcpPort is None:
        tcpPort = int(sys.argv[2])
    if userName is None:
        userName = sys.argv[3]
    if knownNodes is None:
        knownNodes = [('127.0.0.1', 4000)]

    # Set up model with its network node
    model = ad3.models.dht
    dataStore = SQLiteDataStore(dbFile=dbFile)
    node = ad3.models.dht.Node(udpPort=udpPort, tcpPort=tcpPort, dataStore=dataStore)
#    node = entangled.dtuple.DistributedTupleSpacePeer(udpPort=udpPort, dataStore=dataStore)
#    node = entangled.node.EntangledNode(udpPort=udpPort, dataStore=dataStore)
#    node = entangled.kademlia.node.Node(udpPort=udpPort, dataStore=dataStore)


    formatter = logging.Formatter("%(name)s: %(levelname)s %(filename)s:%(lineno)d (in %(funcName)s): %(message)s")
    handler = logging.FileHandler(logFile)
    handler.setFormatter(formatter)
    # set up the kademlia logs
    kademlia_logs.addHandler(handler)
    kademlia_logs.logger.setLevel(logging.DEBUG)
    # set up the tuple space logs
    dtuple_logs = logging.getLogger('dtuple')
    dtuple_logs.addHandler(handler)
    dtuple_logs.setLevel(logging.DEBUG)
    # set up the HTTP logs
    http_logs = logging.getLogger('3ad_http')
    http_logs.addHandler(handler)
    http_logs.setLevel(logging.INFO)
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

    # FIXME: this should not be applied after the node is initialized, but i'm way too lazy right now to do it cleanly.
    node.generate_all_plugin_vectors = controller.generate_all_plugin_vectors

    p.terminalProtocol.namespace['controller'] = controller
    p.terminalProtocol.namespace['userName'] = userName
    p.terminalProtocol.namespace['node'] = controller.model.get_network_handler().node

    return controller

@cont
def clear_network_cache():
    ad3.models.dht.dht._network_handler._cache = {}
    return None

@cont
def print_network_cache():
    n = p.terminalProtocol.namespace
    cache = n['controller'].model.get_network_handler()._cache

    print "\r"
    for x in sorted(cache.keys()):
        print "%s => %r\r\n\r" % (x.encode('hex'), cache[x])
    return None

@cont
def print_data_store():
    n = p.terminalProtocol.namespace
    datastore = n['node']._dataStore

    print "\r"
    for x in sorted(datastore.keys()):
        print "%s => %r\r\n\r" % (x.encode('hex'), datastore[x])
    return None
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
    node = n['controller'].model.get_network_handler().node

    def timeout(failure, i):
        failure.trap(entangled.kademlia.protocol.TimeoutError)
        return i

    for i in range(0, num):
        key = value = str(offset + i)
        df = node.iterativeStore(key, value)

        df.addErrback(timeout, i)

    return None

@sync
@cont
def read_a_bunch_of_data(offset=0, num=1000):
    n = p.terminalProtocol.namespace
    node = n['controller'].model.get_network_handler().node
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
def find_a_bunch_of_data(offset=0, num=1000):
    n = p.terminalProtocol.namespace
    node = n['controller'].model.get_network_handler().node
    outer_df = defer.Deferred()

    done = [0]
    g = [0]
    b = [0]
    def complete():
        done[0] += 1
        if done[0] >= num:
            outer_df.callback(dict(cin=g[0]))

    def timeout(failure, i):
        failure.trap(entangled.kademlia.protocol.TimeoutError)
        b[0] += 1
        complete()
        return i

    def success(val, i):
        if isinstance(val, dict):
            g[0] += 1
        else:
            b[0] += 1
        complete()
        return val

    for i in range(0, num):
        key = str(offset + i)
        df = node.iterativeFindValue(key)
        df.addCallback(success, i)
        df.addErrback(timeout, i)

    return outer_df


@sync
@cont
def add_tags(*args):
    n = p.terminalProtocol.namespace
    ta = TagAggregator(n['controller'], n['controller'].model, args, True)
    df = ta.go()
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
    df = n['controller'].add_file(path, user_name=n['userName'], tags=tags)
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
def get_files(fileName=None, userName=None, tag=None, guessedTag=None, pluginOutput=None):
    """
    @param fileName: if provided, returns only files with a matching file name
    @type  fileName: unicode

    @param userName: if provided, returns only files with a matching user name
    @type  userName: unicode

    @param tag: if provided, returns only files manually tagged with the provided tag
    @type  tag: Tag object

    @param guessedTag: if provided, returns only files automatically tagged with the provided tag
    @type  guessedTag: Tag object

    @param pluginOutput: if provided, returns only the file associated with this output
    @type  pluginOutput: PluginOutput object
    """
    n = p.terminalProtocol.namespace
    if userName is None:
        userName = n['userName']
    if userName is '':
        username = None

    df = n['controller'].model.get_audio_files(file_name=fileName, user_name=userName, tag=tag, guessed_tag=guessedTag, plugin_output=pluginOutput)
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
    df = n['controller'].model.get_tags(name=name, audio_file=audioFile, guessed_file=guessedAudioFile)
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
    df = n['controller'].update_tag_vectors()
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
    df = n['controller'].guess_tags(user_name=n['userName'])
    return df

@sync
@cont
def get_accuracy():
    """
    Returns the accuracy of the system.
    """
    n = p.terminalProtocol.namespace
    real = {}
    guessed = {}
    all_files = {}
    def got_real(files, tag):
        real[tag.key] = [f.key for f in files]

    def got_guessed(files, tag):
        guessed[tag.key] = [f.key for f in files]

    def got_all_files_ever(files, tags):
        all_files['files'] = len(files)
        all_files['tags'] = len(tags)

    def got_tags(tags):
        dfs = []
        for tag in tags:
            t_df = n['controller'].model.get_audio_files(tag=tag, user_name=n['userName'])
            t_df.addCallback(got_real, tag)
            g_df = n['controller'].model.get_audio_files(guessed_tag=tag, user_name=n['userName'])
            g_df.addCallback(got_guessed, tag)
            dfs.append(t_df)
            dfs.append(g_df)

        f_df = n['controller'].model.get_audio_files(user_name=n['userName'])
        f_df.addCallback(got_all_files_ever, tags)
        dfs.append(f_df)

        l_df = defer.DeferredList(dfs)
        return l_df

    def got_all(val):
        potential_correct = 0
        correctly_guessed = 0
        incorrectly_guessed = 0

        for tag in real:
            potential_correct += len(real[tag])
            correctly_guessed += len(
                [f for f in guessed[tag] if f in real[tag]]
            )
            incorrectly_guessed += len(
                [f for f in guessed[tag] if f not in real[tag]]
            )

        return dict(
            potential_correct = potential_correct,
            correctly_guessed = correctly_guessed,
            incorrectly_guessed = incorrectly_guessed,
            potential_incorrect = all_files['files'] * all_files['tags'] - potential_correct,
        )

    df = n['controller'].model.get_tags()
    df.addCallback(got_tags)
    df.addCallback(got_all)
    return df

@cont
def create_db_snapshot(outFile):
    """
    @param outFile: the path to save the database to
    @type  outFile: str

    thanks to: http://osdir.com/ml/python.db.pysqlite.user/2006-01/msg00022.html
    """
    n = p.terminalProtocol.namespace
    ds = n['controller'].model.get_network_handler().node._dataStore
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

@sync
@cont
def create_file_and_tag_vectors():
    """
    Assuming PluginOutput objects exist for every file/plugin pair,
    create file vectors for all files, then create tag vectors based
    on those.
    """
    n = p.terminalProtocol.namespace
    df = n['controller'].mine.calculate_file_and_tag_vectors(user_name=n['userName'])
    return df

@sync
@cont
def add_cal500_files(num=0, tag_em=True, min_examples=5):
    files = {}
    tags = {}
    n = p.terminalProtocol.namespace

    def done(v, results):
        return results, tags

    def got_files(v):
        # parse the results from the wierd format that the controller returns.
        ad3_logs.logger.debug("Got files (%d): %r", len(v), v)
        results = [v[k][0] for k in v if v[k][1]]
#        results = v
        names = [f.file_name for f in results]
        for name in names:
            for tag in files[name]:
                if tag not in tags:
                    tags[tag] = 1
                else:
                    tags[tag] += 1

        if tag_em:
            dfs = []
            for file in results:
                good_tags = [t for t in files[file.file_name] if tags[t] >= min_examples]
                df = n['controller'].tag_files([file], good_tags)
                dfs.append(df)

            df_list = defer.DeferredList(dfs)
            df_list.addCallback(done, results)
            return df_list
        else:
            return results

    # Parse the annotations into a dict of "filename => tag list"
    annotations = open('cal500/annotations')
    lines = [line.strip().split('\t') for line in annotations.readlines()]
    for line in lines:
        name, tag = line
        name = '/Users/anthony/Documents/school/jan_2009/csc466/3ad/scripts/cal500/' + name + '.wav'
        if name not in files:
            files[name] = [tag]
        else:
            files[name].append(tag)

    names = files.keys()

    # pick num random files to add to the system.
    if num > 0:
#        random.shuffle(names)
        names = names[:num]

    #df = n['controller'].model.get_audio_files(user_name=n['userName'])
    df = n['controller'].add_files(names, user_name=n['userName'])
    df.addBoth(got_files)

    return df

@sync
@cont
def remove_untagged_files():
    n = p.terminalProtocol.namespace
    node = n['controller'].model.get_network_handler().node

    def got_tags(tags, file):
        ad3_logs.logger.debug("Got Tags (%d): %r for %r", len(tags), tags, file)
        if len(tags) == 0:
            df_t = remove_file_tuples(file)
            df_f = remove_file(file)
            df_list = defer.DeferredList([df_t, df_f])
            return df_list
        else:
            return None

    def remove_file_tuples(file):
        file_tuple = ("audio_file", file.key, file.file_name, file.user_name)
        df = n['controller'].model._network_handler.dht_remove_tuples(file_tuple)
        return df

    def remove_file(file):
        df = node.iterativeDelete(file.key)
        return df

    def got_files(files):
        ad3_logs.logger.debug("Got Files (%d): %r", len(files), files)
        dfs = []
        for file in files:
            df = n['controller'].model.get_tags(audio_file=file)
            df.addCallback(got_tags, file)
            dfs.append(df)
        df_list = defer.DeferredList(dfs)
        return df_list

    df = n['controller'].model.get_audio_files(user_name=n['userName'])
    df.addBoth(got_files)

    return df

# Complete list of contacts
planet_lab_nodes = [
    ('142.104.21.241', 44000),
    ('142.104.21.245', 44000),
    ('142.104.21.239', 44000),
]
home_nodes = [
    ('24.68.144.250', 4000),
    ('24.68.144.250', 4001)
]
known_nodes = []
known_nodes.extend(planet_lab_nodes)
known_nodes.extend(home_nodes)

# Remove the node itself from each nodes list of contacts.
a_nodes = copy(known_nodes)
a_nodes.remove(('24.68.144.250', 4000))
b_nodes = copy(known_nodes)
b_nodes.remove(('24.68.144.250', 4001))
c_nodes = copy(known_nodes)
#c_nodes.remove(('24.68.144.250', 4002))
p1_nodes = copy(known_nodes)
p1_nodes.remove(('142.104.21.241', 44000))
p3_nodes = copy(known_nodes)
p3_nodes.remove(('142.104.21.245', 44000))
p4_nodes = copy(known_nodes)
p4_nodes.remove(('142.104.21.239', 44000))

#a_nodes = [('127.0.0.1', 4001)]
b_nodes = [('127.0.0.1', 4000)]

cmds = dict(
    test_conn = partial(connect, 4000, 4000, 'anthony', dbFile='bob.sqlite'),
    # Connect from home
    connecta = partial(connect, 4000, 4000, 'user_a', knownNodes=a_nodes, dbFile='a.sqlite', logFile='a.log'),
    connectb = partial(connect, 4001, 4001, 'user_b', knownNodes=b_nodes, dbFile='b.sqlite', logFile='b.log'),
    connectc = partial(connect, 4002, 4002, 'user_c', knownNodes=c_nodes, dbFile='c.sqlite', logFile='c.log'),
    # Connect from planet lab
    connectp1 = partial(connect, 44000, 44000, 'user_p1', knownNodes=p1_nodes, dbFile='p.sqlite', logFile='p.log'),
    connectp3 = partial(connect, 44000, 44000, 'user_p3', knownNodes=p3_nodes, dbFile='p.sqlite', logFile='p.log'),
    connectp4 = partial(connect, 44000, 44000, 'user_p4', knownNodes=p4_nodes, dbFile='p.sqlite', logFile='p.log'),

    add_bobs_files = partial(add_files, [
        "/Users/anthony/Documents/3ad_audio/new_audio/bob's audio/Aries' Theme.wav",
        "/Users/anthony/Documents/3ad_audio/new_audio/bob's audio/Bach - Suite for Violoncello Solo No. 3 in C major BWV 1009 - I. Prelude.wav",
#        "/Users/anthony/Documents/3ad_audio/new_audio/bob's audio/Bach - Suite for Violoncello Solo No. 3 in C major BWV 1009 - II. Allemande.wav",
#        "/Users/anthony/Documents/3ad_audio/new_audio/bob's audio/Bach - Suite for Violoncello Solo No. 3 in C major BWV 1009 - III. Courante.wav",
#        "/Users/anthony/Documents/3ad_audio/new_audio/bob's audio/Bach - Suite for Violoncello Solo No. 3 in C major BWV 1009 - IV. Sarabande.wav",
#        "/Users/anthony/Documents/3ad_audio/new_audio/bob's audio/Bach - Suite for Violoncello Solo No. 3 in C major BWV 1009 - V. Bourrees I & II.wav",
#        "/Users/anthony/Documents/3ad_audio/new_audio/bob's audio/Legebit.wav",
#        "/Users/anthony/Documents/3ad_audio/new_audio/bob's audio/Night of Silence.wav",
#        "/Users/anthony/Documents/3ad_audio/new_audio/bob's audio/Nuages 1.wav",
#        "/Users/anthony/Documents/3ad_audio/new_audio/bob's audio/Nuages 2.wav",
#        "/Users/anthony/Documents/3ad_audio/new_audio/bob's audio/Nuages 3.wav",
#        "/Users/anthony/Documents/3ad_audio/new_audio/bob's audio/Nuages 4.wav",
#        "/Users/anthony/Documents/3ad_audio/new_audio/bob's audio/Nuages 5.wav",
#        "/Users/anthony/Documents/3ad_audio/new_audio/bob's audio/Terra's Theme.wav",
#        "/Users/anthony/Documents/3ad_audio/new_audio/bob's audio/Theme to Voyager.wav",
#        "/Users/anthony/Documents/3ad_audio/new_audio/bob's audio/_01 Johann Sebastian Bach - Suite for Lute in E minor BWV 996 - Allemande 1.mp3.wav",
#        "/Users/anthony/Documents/3ad_audio/new_audio/bob's audio/_01 Johann Sebastian Bach - Suite for Lute in E minor BWV 996 - Allemande.mp3.wav",
#        "/Users/anthony/Documents/3ad_audio/new_audio/bob's audio/_02 Johann Sebastian Bach - Partita for Lute in C minor BWV 997 - Sarabande.mp3.wav",
#        "/Users/anthony/Documents/3ad_audio/new_audio/bob's audio/_03 Johann Sebastian Bach - Partita for Lute in C minor BWV 997 - Gigue.mp3.wav",
#        "/Users/anthony/Documents/3ad_audio/new_audio/bob's audio/_04 Johann Sebastian Bach - Partita for Violin Solo No. 1 in B minor BWV 1002 - Sarabande.mp3.wav",
#        "/Users/anthony/Documents/3ad_audio/new_audio/bob's audio/_05 Johann Sebastian Bach - Partita for Violin Solo No. 1 in B minor BWV 1002 - Bourree.mp3.wav",
#        "/Users/anthony/Documents/3ad_audio/new_audio/bob's audio/_06 Johann Sebastian Bach - Partita for Violin Solo No. 1 in B minor BWV 1002 - Double.mp3.wav",
    ]),
    a_nodes=a_nodes,
    add_cal500_files=add_cal500_files,
    create_file_and_tag_vectors=create_file_and_tag_vectors,
    add_tags=add_tags,
    clear_network_cache=clear_network_cache,
    print_network_cache=print_network_cache,
    print_data_store=print_data_store,
    sync = sync,
    add_file=add_file,
    add_files=add_files,
    get_accuracy=get_accuracy,
    get_files=sync(get_files),
    get_tags=sync(get_tags),
    print_file=sync(print_file),
    print_files=print_files,
    update_tag_vectors=update_tag_vectors,
    update_file_vector=update_file_vector,
    update_predictions=update_predictions,
    create_db_snapshot=create_db_snapshot,
    store_a_bunch_of_data=store_a_bunch_of_data,
    read_a_bunch_of_data=read_a_bunch_of_data,
    find_a_bunch_of_data=find_a_bunch_of_data,
    remove_untagged_files=remove_untagged_files,
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
    import cProfile
    cProfile.run('reactor.run()', 'cProfile.output')
#    reactor.run()
finally:
    termios.tcsetattr(fd, termios.TCSANOW, oldSettings)
    os.write(fd, "\r\x1bc\r")

