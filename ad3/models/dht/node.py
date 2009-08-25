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
        self.computations = {}

    def joinNetwork(self, knownNodeAddresses=None):
        entangled.dtuple.DistributedTupleSpacePeer.joinNetwork(
            self, knownNodeAddresses=knownNodeAddresses
        )

        self._oobServerFactory = protocol.HTTPServerFactory()
        self._oobListeningPort = \
            listenTCP(self.tcpPort, self._oobServerFactory)

    def sendOffloadCommand(self, key, struct):
        """ Will set up oobServerFactory to accept download requests for
        the file described in C{struct} and issue the offload command
        to the nearest available contact.

        Will query at most protocol.k contacts, as per the method
        C{self.iterativeFindNode}.

        Immediately returns a deferred that will return either C{True} or
        C{False} depending on whether the command was accepted by a remote
        node.
        """
        contacts = []
        outer_df = defer.Deferred()

        def executeRPC():
            contact = contacts.pop(0)
            logger.debug("SENDING RPC TO: %r; % contacts left",
                    contact, len(contacts))
            struct['contact'] = contact

            # Tell our server factory to accept this request.
            self._oobServerFactory.add_request_key(key, struct['file_uri'])

            # Ask the contact to do it.
            rpc_df = contact.offload(key, struct['file_key'],
                    struct['file_uri'])

            rpc_df.addBoth(receiveResponse)

            return rpc_df

        def receiveResponse(response):
            if len(contacts) > 0 and response != "OK":
                # If the request wasn't accepted, but we still have more
                # contacts to try, do so.
                executeRPC()
            else:
                # If the file was downloaded, the request will have been
                # automatically removed from the server's ACL thing. But lets
                # make sure:
                try: self._oobServerFactory.get_request_key(key)
                except KeyError, e: pass

                # We're done. Trigger the outer deferred.
                outer_df.callback(response)

        def gotNodes(nodes):
            contacts.extend(nodes)
            receiveResponse('begin')

        # Find k nodes closest to the key...
        inner_df = self.iterativeFindNode(key)
        inner_df.addCallback(gotNodes)

        return outer_df

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
    def offload(self, key, file_key, file_uri,
            _rpcNodeID, _rpcNodeContact, **kwargs):
        """ RPC method to request that this node performs a vector computation
        for the requesting node.

        If the request is accepted, this method will continue by downloading
        the file in question from the remote node, collecting all plugins,
        creating plugin outputs for the plugin, file_key pair, and updating
        self.computations[key] with the resulting vector from the learning
        module.

        At each stage, self.computations[key] will be updated, so that this
        node is able to respond to poll() requests.
        """
        logger.debug("Received an offload RPC - %r; %r",
                file_uri, _rpcNodeContact)

        if len(self.computations) > 0:
            logger.debug("DECLINING offload request")
            # If we are already processing something, decline this request
            return "NO"

        logger.debug("ACCEPTING offload request")
        self.computations[key] = {
            'complete': False,
            'vector': None,
            'failed': False,
            'downloaded': False
        }

        def do_computation(file):
            #FIXME: THIS METHOD needs to be rewritten. The rest of the offload() method is fine, tho.
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

        def downloaded_file(file):
            logger.debug("Finished downloading %s", file_uri)
            df = threads.deferToThread(do_computation, file)

        def download_file(file):
            # Receive the file in the main loop, but spin processing off
            # into its own thread.
            logger.debug("Downloading %s", file_uri)
            clientFactory = HTTPClientFactory(
                    downloaded_file, key, file_uri, timeout=0)
            reactor.connectTCP(
                    _rpcNodeContact.address, self.tcpPort, clientFactory)

        download_file()

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

