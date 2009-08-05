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
import twisted.internet.protocol as tip
import twisted.web.http as twh
from twisted.web.http_headers import Headers
from functools import partial

class OOBServerProtocol(tip.Protocol):
    def __init__(self, node):
        self.node = node

    def dataReceived(self, data):
        """ Called when server receives data """
        # decode request message
        # if node.checkPendingOOBRequest(contact, file_key)
        # then respond with the file length and start sending the file ( using self.transport.write() )
        # else terminate the connection self.transport.loseConnection()

    def connectionMade(self):
        """ Received connection from client """


class OOBClientProtocol(tip.Protocol):
    def __init__(self, node, file_key):
        self.node = node
        self.file_key = file_key

    def dataReceived(self, data):
        """ Called when Client receives data """
        # decode response message (file size)
        # receive file
        # terminate connection

    def connectionMade(self):
        """ Connected to server """
        # send request file URI (incl self.node.address and self.node.port)

class ServerFactory(tip.ServerFactory):
    def __init__(self, node, protocol=OOBServerProtocol):
        self.protocol = protocol
        self.node = node

    def buildProtocol(self, addr):
        p = self.protocol(node=self.node)
        p.factory = self
        return p

class ClientFactory(tip.ClientCreator):
    def __init__(self, reactor, protocolClass=OOBClientProtocol, *args, **kwargs):
        tip.ClientCreator.__init__(
            self, reactor, protocolClass, *args, **kwargs)

    def connectTCP(self, host, port, timeout=30, bindAddress=None, **kwargs):
        """Connect to remote host, return Deferred of resulting protocol instance."""
        d = defer.Deferred()
        new_kwargs = {}
        new_kwargs.update(self.kwargs)
        new_kwargs.update(kwargs)
        instance = self.protocolClass(*self.args, **new_kwargs)
        f = _InstanceFactory(self.reactor, instance, d)
        self.reactor.connectTCP(host, port, f,
            timeout=timeout, bindAddress=bindAddress)
        return d
