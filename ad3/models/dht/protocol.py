#import ad3.models.abstract
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
import twisted.web.client as twc

class Request(twh.Request):
    """Created by the HTTPServer to service a requeset from an HTTPClient"""
    def __init__(self, channel, queued):
        twh.Request.__init__(self, channel, queued)

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
            self.write(chunk)
            if len(chunk) < chunk_size:
                break


class HTTPServer(twh.HTTPChannel):
    """
    The only purpose of this server is to spin off a Request object
    when a new request is received on an existing connection
    """
    requestFactory = Request


class HTTPServerFactory(twh.HTTPFactory):
    """
    The only purpose of this factory is to spin off a Server object
    when a new connection is received
    """
    protocol = HTTPServer


class HTTPClient(twh.HTTPClient):
    """
    This client class is responsible for sending request headers,
    parsing response headers, and receiving response data into a buffer.

    In the normal Twisted code (eg twc.HTTPPageGetter, twc.HTTPPageDownloader),
    most of this function is carried out by the Factory object.

    This seems like a hideous blurring of responsibility to me, so we
    encapsulate what simple options we need here.
    """
    def __init__(self, filename=None):
        self.receivingFile = False

    def sendFileRequest(self, filename):
        self.sendCommand('GET', filename)
        self.sendHeader('x-awesome', 'srsly oh yea')
        self.endHeaders()

    def connectionMade(self):
        self.sendFileRequest(self.factory.path)

    def handleHeader(self, key, val):
        # If this is going to be a file, accept it
        if key.lower() == 'x-sending-file':
            self.receivingFile = True

    def handleEndHeaders(self):
        #self.factory.gotHeaders(self.headers)
        pass

    def handleResponseEnd(self):
        # SUCCESS. Response finished.
        if self.receivingFile:
            # Terminate the connection.
            # Send the self.__buffer file to marsyas for analysis!
            self.__buffer.seek(0)
            print "BEGIN FILE"
            print self.__buffer.read()
            print "EOF RECEIVED"
            pass

    def lineReceived(self, line):
        if not self.firstLine and not line:
            # Catch the first blank line after the first line:
            # this will be the end of our headers.
            # Time to start reading data!
            # First, lets override default stringIO() buffer with a file:
            self.__buffer = tempfile.NamedTemporaryFile()
            self.handleEndHeaders()
            self.setRawMode()
        else:
            # otherwise, keep reading headers
            twh.HTTPClient.lineReceived(self, line)

class HTTPClientFactory(twc.HTTPClientFactory):
    """
    The only purpose of this factory is to create an HTTPClient object
    that will handle the request.

    Instantiation arguments:
        url
        method='GET'
        postdata=None
        headers=None
        agent="Twisted PageGetter"
        timeout=0
        cookies=None
        followRedirect=1
        redirectLimit=20

    This class also takes care
    """
    protocol = HTTPClient


import sys
if __name__ == "__main__":
    client = len(sys.argv) > 1
    hostname = 'localhost'
    port = 4000
    file = '/Users/anthony/cp.sh'
    url = 'http://%s:%d%s' % (hostname, port, file)

    if client:
        reactor.connectTCP(hostname, port, HTTPClientFactory(url, timeout=0))
    else:
        reactor.listenTCP(port, HTTPServerFactory())
    reactor.run()
