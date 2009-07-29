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
from functools import partial
from .. import logs
logger = logs.logger

class MyProtocol(entangled.kademlia.protocol.KademliaProtocol):
    def sendRPC(self, contact, method, args, rawResponse=False):
        logger.debug("-->> myprotocol: sendRPC(%r, %s)", contact, method)
        outer_df = defer.Deferred()

        def error(failure):
            logger.debug("myprotocol: ERROR %r", failure)
            outer_df.errback(failure)
            return failure

        def got_response(val):
            logger.debug("myprotocol: GOT RESPONSE %r", val)
            outer_df.callback(val)
            return val

        def actually_send(val):
            logger.debug("myprotocol: SENDING (%s, %r, %r)", method, args, rawResponse)
            df = KademliaProtocol.sendRPC(self, contact, method, args, rawResponse)
            return df

        # the deferred returned by this is what _dht_df waits for
        # it should get called back as soon as we get a response message
        def handle_dfs(val):
            logger.debug("<<---------->>")
            logger.debug("myprotocol: HANDLING DFS")
            df = defer.Deferred()
            def done(val):
                logger.debug("myprotocol: DONE")
                import time
                time.sleep(0.1)
                logger.debug("myprotocol: Continuing...")
                df.callback(None)

            inner_df = defer.Deferred()
            inner_df.addCallback(actually_send)
            inner_df.addCallback(got_response)
            inner_df.addErrback(error)
            inner_df.addBoth(done)
            inner_df.callback(None)

            return df

        # should execute immediately
        _dht_df.addCallback(handle_dfs)

        # should get called back as soon as msg returns.
        logger.debug("--<< myprotocol: RETURNING outer_df")
        return outer_df

