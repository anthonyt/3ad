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
import twisted.web.http as twh
from twisted.web.http_headers import Headers
from functools import partial

class Request(twh.Request):
    """Created by the HTTPServer to service a requeset from an HTTPClient"""
    def __init__(self, channel, queued):
        twh.Request(self, channel, queued)

        self.server = self.channel

    def process(self):
        """
        Called when a request completes (and all data is received)
        """
        self.requestHeaders.hasHeader('x-awesome')
        awesomes = self.requestHeaders.getRawHeaders('x-awesome', [])
        content = self.content
        method = self.method # (get, post, etc)
        path = self.path

        length = os.path.getsize(path)
        self.setHeader('content-length', str(int(length)))
        self.setHeader('content-type', 'application/octet-stream')
        # alternately audio/x-wav or audio/mpeg or audio/x-aiff
        self.setHeader('x-sending-file', 'True')
        file = open(path, 'rb')

        # send the file in 4kb chunks
        chunk_size = 4096
        while True:
            chunk = file.read(chunk_size)
            welf.write(chunk)
            if len(chunk) < chunk_size:
                break


class HTTPServer(twh.HTTPChannel):
    """ The only purpose of this server is to spin off a Request object when a new request is received on an existing connection """
    requestFactory = Request

    def __init__(self):
        twh.HTTPChannel.__init__(self)


class HTTPServerFactory(twh.HTTPFactory):
    """ The only purpose of this factory is to spin off a Server object when a new connection is received """
    protocol = HTTPServer

    def __init__(self, logPath=None, timeout=60*60*12):
        twh.HTTPFactory.__init__(self, logPath, timeout)


class HTTPClient(twh.HTTPClient):
    def __init__(self, filename):
        self.receivingFile = False

    def sendFileRequest(self, filename):
        self.sendCommand('GET', filename)
        self.sendHeader('x-awesome', 'srsly oh yea')
        self.endHeaders()

    def handleHeader(self, key, val):
        # If this is going to be a file, accept it
        if key == 'x-sending-file':
            self.receivingFile = True

    def handleResponseEnd(self):
        # SUCCESS. Response finished.
        if self.receivingFile:
            # Terminate the connection.
            # Send the self.__buffer file to marsyas for analysis!
            pass

    def lineReceived(self, line):
        # override default stringIO() buffer with a file
        if not self.firstLine and not line:
            self.__buffer = tempfile.NamedTemporaryFile()
            self.handleEndHeaders()
            self.setRawMode()
        else:
            twh.HTTPClient.lineReceived(self, line)

