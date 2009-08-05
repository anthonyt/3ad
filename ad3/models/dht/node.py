# system
import simplejson
import random
from functools import partial
# entangled
import entangled
import entangled.dtuple
from entangled.kademlia.node import rpcmethod
# twisted
from twisted.internet.reactor import listenTCP
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import threads
# 3ad
import protocol
import logging
logger = logging.getLogger('3ad')

class Node(entangled.dtuple.DistributedTupleSpacePeer):
    def __init__(self, id=None, udpPort=4000, tcpPort=4000,
                 dataStore=None, routingTable=None,
                 networkProtocol=None):

        entangled.dtuple.DistributedTupleSpacePeer.__init__(
            self, id=id, udpPort=udpPort, dataStore=dataStore,
            routingTable=routingTable, networkProtocol=networkProtocol
        )

        self.tcpPort = tcpPort
        self._oobListeningPort = None
        self._oobServerFactory = None

    def joinNetwork(self, knownNodeAddresses=None):
        entangled.dtuple.DistributedTupleSpacePeer.joinNetwork(
            self, knownNodeAddresses=knownNodeAddresses
        )

        self._oobServerFactory = protocol.HTTPServerFactory()
        self._oobListeningPort = \
            listenTCP(self.tcpPort, self._oobServerFactory)

    def sendOffloadCommand(self, key, struct):
        def executeRPC(nodes):
            contact = random.choice(nodes)
            logger.debug("SENDING RPC TO: %r", contact)
            struct['contact'] = contact

            df = contact.offload(key, struct['file_uri'])
            return df

        # Find k nodes closest to the key...
        df = self.iterativeFindNode(key)
        df.addCallback(executeRPC)

        return df

    def pollOffloadedCalculation(self, key, struct):
        def update_struct(val):
            response = simplejson.loads(val)
            struct['complete'] = response['complete']
            struct['failed'] = response['failed']
            struct['vector'] = response['vector']

        df = struct['contact'].poll(key, struct['file_uri'])
        df.addCallback(update_struct)

        return df

    @rpcmethod
    def offload(self, key, file_uri, _rpcNodeID, _rpcNodeContact, **kwargs):
        logger.debug("-------------")

        logger.debug("RECEIVED AN OFFLOAD RPC! %r %r", file_uri, plugin_module)

        if not hasattr(self, 'computations'):
            self.computations = {}

        self.computations[key] = {
            'complete': False,
            'vector': None,
            'failed': False,
            'downloaded': False
        }

        def do_computation(file):
            try:
                # In a perfect world there would only be one thread mucking
                # about with self.computations[key] at the same time. So
                # hopefully we don't have to use mutexes.
                self.computations[key]['downloaded'] = True

                logger.debug("Computing vector for %s", file_name)

                # Here's the real work: creating the vector.
                vector = plugin.create_vector(file.name)

                if len(vector) == 0 or\
                        len([a for a in vector if a == 0]) == len(vector):
                    # Zero length vector or zeroed out vector is an indication
                    # that Marsyas choked.
                    self.computations[key]['failed'] = True

                self.computations[key]['complete'] = True
                self.computations[key]['vector'] = vector
            except Exception:
                logger.debug("Computation error :( %s",
                        failure.getErrorMessage())
                self.computations[key]['complete'] = True
                self.computations[key]['failed'] = True

        def callback(file):
            df = threads.deferToThread(do_computation, file)

        # Receive the file in the main loop, but spin processing off
        # into its own thread.
        logger.debug("Downloading %s", file_uri)
        clientFactory = HTTPClientFactory(
                callback, key, file_uri, timeout=0)
        reactor.connectTCP(
                _rpcNodeContact.address, self.tcpPort, clientFactory)

        logger.debug("OFFLOAD FINISHED")
        return "OK"

    @rpcmethod
    def poll(self, key, file_uri, _rpcNodeID, _rpcNodeContact, **kwargs):
        if not hasattr(self, 'computations') or not self.computations.has_key(key):
            # we've never heard of the requested offload operation. make something up!
            logger.debug("Returning BS poll")
            result = {'complete': True, 'vector': None, 'failed': True, 'downloaded': False}
        elif self.computations[key]['complete']:
            # we've finished the requested offload operation. remove if from the list and return it
            logger.debug("Returning finished poll")
            result = self.computations.pop(key)
        else:
            # we haven't finished the requested offload operation, but we have some data on it
            logger.debug("Returning unfinished poll")
            result = self.computations[key]

        return simplejson.dumps(result)

