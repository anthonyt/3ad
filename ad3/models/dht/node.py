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
from twisted.internet.protocol import ServerFactory
from twisted.internet.reactor import listenTCP
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import threads
from functools import partial
import protocol
import logging
logger = logging.getLogger('3ad')

class Node(entangled.dtuple.DistributedTupleSpacePeer):
    def sendOffloadCommand(self, key, struct):
        hash = {
            'module_name': struct['module_name'],
            'file_uri': struct['file_uri']
        }
        value = simplejson.dumps(hash)

        def executeRPC(nodes):
            contact = random.choice(nodes)
            logger.debug("SENDING RPC TO: %r", contact)
            struct['contact'] = contact

            df = contact.offload(key, value, self.id)
            return df

        # Find k nodes closest to the key...
        df = self.iterativeFindNode(key)
        df.addCallback(executeRPC)

        return df

    def pollOffloadedCalculation(self, key, struct):
        hash = {
            'module_name': struct['module_name'],
            'file_uri': struct['file_uri']
        }
        value = simplejson.dumps(hash)

        def update_struct(val):
            response = simplejson.loads(val)
            struct['complete'] = response['complete']
            struct['failed'] = response['failed']
            struct['vector'] = response['vector']

        df = struct['contact'].poll(key, value, self.id)
        df.addCallback(update_struct)

        return df

    @rpcmethod
    def offload(self, key, value, originalPublisherID=None, **kwargs):
        logger.debug("-------------")
        hash = simplejson.loads(value)

        plugin_module = hash['module_name']
        file_uri = hash['file_uri']
        id = plugin_module + file_uri
        logger.debug("RECEIVED AN OFFLOAD RPC! %r %r", file_uri, plugin_module)

        if not hasattr(self, 'computations'):
            self.computations = {}

        self.computations[id] = {
            'complete': False,
            'vector': None,
            'failed': False,
            'downloaded': False
        }

        def do_computation():
            try:
                plugin = Plugin('temp', plugin_module)

                logger.debug("Downloading %s", file_uri)
                (file_name, headers) = urllib.urlretrieve('http://'+urllib.quote(file_uri[7:]))
                self.computations[id]['downloaded'] = True

                logger.debug("Computing vector for %s", file_name)
                vector = plugin.create_vector(file_name)
                if len(vector) == 0 or len([a for a in vector if a == 0]) == len(vector):
                    # Zero length vector or zeroed out vector is an indication that Marsyas choked.
                    self.computations[id]['failed'] = True
                self.computations[id]['complete'] = True
                self.computations[id]['vector'] = vector

                os.remove(file_name)
            except Exception:
                logger.debug("Computation error :( %s", failure.getErrorMessage())
                self.computations[id]['complete'] = True
                self.computations[id]['failed'] = True
            finally:
                return None

        df = threads.deferToThread(do_computation)

        #file = tempfile.NamedTemporaryFile(suffix=key.encode('hex'))
        #file.write(value)
        logger.debug("OFFLOAD FINISHED")
        return "OK"

    @rpcmethod
    def poll(self, key, value, originalPublisherID=None, age=0, **kwargs):
        hash = simplejson.loads(value)
        plugin_module = hash['module_name']
        file_uri = hash['file_uri']
        id = plugin_module + file_uri

        if not hasattr(self, 'computations') or not self.computations.has_key(id):
            # we've never heard of the requested offload operation. make something up!
            logger.debug("Returning BS poll")
            result = {'complete': True, 'vector': None, 'failed': True, 'downloaded': False}
        elif self.computations[id]['complete']:
            # we've finished the requested offload operation. remove if from the list and return it
            logger.debug("Returning finished poll")
            result = self.computations.pop(id)
        else:
            # we haven't finished the requested offload operation, but we have some data on it
            logger.debug("Returning unfinished poll")
            result = self.computations[id]

        return simplejson.dumps(result)

