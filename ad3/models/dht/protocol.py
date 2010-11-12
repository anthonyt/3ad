# system
import tempfile
import os
import mutex
import urllib
# entangled
import entangled
import entangled.dtuple
# twisted
from twisted.internet import reactor
import twisted.web.http as twh
import twisted.web.client as twc

import logging
logger = logging.getLogger('3ad_http')

class Request(twh.Request):
    """Created by the HTTPServer to service a requeset from an HTTPClient"""
    def __init__(self, channel, queued):
        twh.Request.__init__(self, channel, queued)

        self.server = self.channel

    def process(self):
        logger.debug("Serving: %r", self.path)
        """
        Called when a request completes (and all data is received)
        """
        # Make sure this request had a useful request_key
        request_keys = self.requestHeaders.getRawHeaders('x-request-key', None)
        if not request_keys:
            logger.debug("No request keys were set in this request.")
            return
        request_key = request_keys[0]

        # make sure that the request_key is one we're waiting for.
        # try to remove it from the list of pending request_keys
        requested_file = self.server.factory.get_request_key(request_key)
        if not requested_file:
            logger.debug("Requested file %r was not set to readable.", request_key)
            return

        # Make sure the file requested by the client (self.path) is the one we
        # wanted to give them (requested_file).
        if not requested_file == self.path:
            logger.debug("Client requested %r, but I was prepared to serve %r",
                    self.path, requested_file)
            return

        # If we got here, we know that this was a valid and pending request
        content = self.content
        method = self.method # (get, post, etc)
        file_name = urllib.unquote(self.path)

        # Set our headers
        # TODO: Maybe specify content-type as audio/x-wav, audio/mpeg, etc.
        length = os.path.getsize(file_name)
        self.setHeader('content-length', str(int(length)))
        self.setHeader('content-type', 'application/octet-stream')

        # Read the file and send it in 4kb chunks
        file = open(file_name, 'rb')
        chunk_size = 4096
        while True:
            chunk = file.read(chunk_size)
            self.write(chunk)
            if len(chunk) < chunk_size:
                # TODO: Find out if this is true:
                # I'm assuming that if a read succeeds, but returns less than
                # the maximum number of bytes, it signifies, in python, that
                # we have reached the end of the file.
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

    def __init__(self, *args, **kwargs):
        twh.HTTPFactory.__init__(self, *args, **kwargs)

        self._pending_request_keys = dict()
        self._prk_mux = mutex.mutex()

    def _unsafe_add_request_key(self, kf_tuple):
        key, file_name = kf_tuple
        self._pending_request_keys[key] = file_name
        self._prk_mux.unlock()

    def _unsafe_get_request_key(self, ks_tuple):
        key, struct = ks_tuple
        struct[0] = self._pending_request_keys.pop(key, None)
        self._prk_mux.unlock()

    def add_request_key(self, key, file_name):
        # TODO: Add a timeout, so that no key can sit in the list for longer
        # than x seconds
        logger.debug("Adding request key: %r -> %r", key, file_name)
        return self._prk_mux.lock(
                self._unsafe_add_request_key, (key, file_name)
        )

    def get_request_key(self, key):
        struct = [0]
        self._prk_mux.lock(
                self._unsafe_get_request_key, (key, struct)
        )
        logger.debug("Getting request key: %r -> %r", key, struct[0])
        return struct[0]


class HTTPClient(twh.HTTPClient):
    """
    This client class is responsible for sending request headers,
    parsing response headers, and receiving response data into a buffer.

    In the normal Twisted code (eg twc.HTTPPageGetter, twc.HTTPPageDownloader),
    most of this function is carried out by the Factory object.

    This seems like a hideous blurring of responsibility to me, so we
    encapsulate what simple options we need here.
    """
    def __init__(self):
        self.receivingFile = False

    def sendFileRequest(self, filename):
        logger.debug("Sending file request; GET %r", filename)
        self.sendCommand('GET', filename)
        self.sendHeader('x-request-key', self.factory.request_key)
        self.endHeaders()

    def connectionMade(self):
        self.sendFileRequest(self.factory.path)

    def handleHeader(self, key, val):
        # Handle individual header lines
        pass

    def handleEndHeaders(self):
        #self.factory.gotHeaders(self.headers)
        pass

    def handleStatus(self, version, status, message):
        """
        Called when the status-line is received.

        @param version: e.g. 'HTTP/1.0'
        @param status: e.g. '200'
        @type status: C{str}
        @param message: e.g. 'OK'
        """
        logger.debug("Got status %r: %r", status, message)
        if status == '200':
            self.receivingFile = True

    def handleResponseEnd(self):
        # SUCCESS. Response finished.
        if self.receivingFile and self.__buffer is not None:
            # Send the self.__buffer file to marsyas for analysis!
            self.__buffer.seek(0)
            self.factory.callback(self.__buffer)
            self.__buffer = None

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
        callback
        key
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

    def __init__(self, callback, key, url, method='GET', postdata=None,
                 headers=None, agent="Twisted PageGetter", timeout=0,
                 cookies=None, followRedirect=1, redirectLimit=20):
        """Initialize the Client Factory (builder)

        Additional parameter "callback" is expected to be a function that takes
        a single file object as an argument.

        It will be called with the received file as an argument, if receipt of
        the file is successful.

        Additional parameter "key" is expected to be an ascii-encoded byte string
        that will uniquely identify the request.
        """

        twc.HTTPClientFactory.__init__(self, url, method, postdata, headers,
                agent, timeout, cookies, followRedirect, redirectLimit)

        self.callback = callback
        self.request_key = key

    def clientConnectionLost(self, connector, reason):
        logger.debug('Lost connection.  Reason: %r', reason)
        twc.HTTPClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        logger.debug('Connection failed. Reason: %r', reason)
        twc.HTTPClientFactory.clientConnectionFailed(self, connector, reason)



import sys
def mycallback(file):
    print "<<< EOF"
    print file.read()
    print "EOF"

if __name__ == "__main__":
    console = logging.StreamHandler()
    logger.addHandler(console)
    logger.setLevel(logging.DEBUG)

    client = len(sys.argv) > 1
    hostname = 'localhost'
    hostname = '127.0.0.1'
    port = 4000
    file = '/Users/anthony/cp.sh'
    url = 'http://%s:%d%s' % (hostname, port, file)
    print "Requesting", url
    url = file

    clientKey = 'abcdefg'
    serverKeys = dict(zomg='not the file', bob='jimmy', abcdefg=file)

    if client:
        print "Requesting", url
        clientFactory = HTTPClientFactory(mycallback, clientKey, url, timeout=0)
        reactor.connectTCP(hostname, port, clientFactory)
    else:
        serverFactory = HTTPServerFactory()
        for k in serverKeys:
            serverFactory.add_request_key(k, serverKeys[k])
        reactor.listenTCP(port, serverFactory)

    reactor.run()

