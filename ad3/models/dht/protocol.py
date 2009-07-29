import ad3.models.abstract
import simplejson
import hashlib
import urllib
import tempfile
import random
import os
import entangled
import entangled.dtuple
import entangled.kademlia.contact
import entangled.kademlia.msgtypes
from entangled.kademlia.node import rpcmethod
from entangled.kademlia.protocol import KademliaProtocol
from time import time
from sets import Set
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import threads
from twisted.internet.protocol import Protocol
from functools import partial

class OOBProtocol(Protocol):
    """This is just about the simplest possible
    protocol"""

    def dataReceived(self, data):
        if data == 1:
            print data

    def connectionMade(self):
        print "Client Connected to server"

    def main():
        """This runs the protocol on port 8000"""
        factory = protocol.ServerFactory()
        factory.protocol = Echo
        reactor.listenTCP(8000,factory)
        reactor.run()

