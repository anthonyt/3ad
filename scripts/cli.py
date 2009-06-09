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

from functools import partial
from IPython.completer import Completer

from twisted.internet import selectreactor
from twisted.internet import reactor
from twisted.internet import defer
from twisted.internet import stdio
from twisted.conch.insults.insults import ServerProtocol
from twisted.conch.manhole import Manhole

# ensure the main ad3 module is on the path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
        sys.path.append(parent_dir)

import ad3
import ad3.models
import ad3.models.dht
from ad3.models.dht import AudioFile, Plugin
from ad3.learning import *
from ad3.learning.euclid import Euclidean
from ad3.learning.gauss import Gaussian
from ad3.learning.svm import SVM
from ad3.controller import Controller

defer.setDebugging(True)

class ConsoleManhole(Manhole):
    def __init__(self, namespace=None):
        Manhole.__init__(self, namespace)
        self.completer = Completer(namespace=self.namespace)
        self.completeState = 0
        self.lastTabbed = ''
        self.lastSuggested = ''

    def connectionLost(self, reason):
        reactor.stop()

    def connectionMade(self):
        Manhole.connectionMade(self)

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


def connect(udpPort=None, userName=None, knownNodes=None):

    if udpPort is None:
        udpPort = int(sys.argv[1])
    if userName is None:
        userName = sys.argv[2]
    if knownNodes is None:
        knownNodes = [('127.0.0.1', 4000)]

    # Set up model with its network node
    model = ad3.models.dht,
    node = ad3.models.dht.MyNode(udpPort=udpPort)
    print "->", "joining network..."
    node.joinNetwork(knownNodes)
    print "->", "joined network..."
    # create a newtwork handler using the network node
    nh = ad3.models.dht.NetworkHandler(node)
    # Set the network handler for the model.
    ad3.models.dht.set_network_handler(nh)

    # Set up the classifier
    gaussian = Gaussian(model, 100)

    # Set up the controller
    controller = Controller(model, gaussian)

    return controller

namespace = dict(
    __name__ = '__console__',
    __doc__ = None,
    connect = connect
)

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

