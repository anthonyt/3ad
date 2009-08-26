# system
import os
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

    def sendOffloadCommand(self, struct):
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
            logger.debug("SENDING RPC TO: %r; %d contacts left",
                    contact, len(contacts))
            struct['contact'] = contact

            # Tell our server factory to accept this request.
            self._oobServerFactory.add_request_key(
                    struct['file_key'], struct['file_uri'])

            # Ask the contact to do it.
            rpc_df = contact.offload(
                    struct['file_key'], struct['file_uri'])

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
                if response != "OK":
                    try: self._oobServerFactory.get_request_key(struct['file_key'])
                    except KeyError, e: pass

                # We're done. Trigger the outer deferred.
                outer_df.callback(response)

        def gotNodes(nodes):
            contacts.extend(nodes)
            receiveResponse('begin')

        # Find k nodes closest to the key...
        inner_df = self.iterativeFindNode(struct['file_key'])
        inner_df.addCallback(gotNodes)

        return outer_df

    def pollOffloadedCalculation(self, struct):
        df = struct['contact'].poll(struct['file_key'])
        return df

    @rpcmethod
    def offload(self, file_key, file_uri,
            _rpcNodeID, _rpcNodeContact, **kwargs):
        """ RPC method to request that this node performs a vector computation
        for the requesting node.

        If the request is accepted, this method will continue by downloading
        the file in question from the remote node, collecting all plugins,
        creating plugin outputs for the plugin, file_key pair, and updating
        self.computations[file_key] with the resulting vector from the learning
        module.

        At each stage, self.computations[file_key] will be updated, so that this
        node is able to respond to poll() requests.
        """
        logger.debug("Received an offload RPC - %r; %r",
                file_uri, _rpcNodeContact)

        if len(self.computations) > 0:
            logger.debug("DECLINING offload request")
            # If we are already processing something, decline this request
            return "NO"

        logger.debug("ACCEPTING offload request")
        self.computations[file_key] = {
            'complete': False,
            'vectors': None,
            'failed': False,
            'downloaded': False
        }

        def got_vectors(results):
            # Everything looks good, so far. Results is a dict of vectors.
            logger.debug("Computed vectors for %s", file_uri)

            # Check for any obvious errors from Marsyas:
            for t in results:
                vector = results[t]
                # FIXME: The following checks should be handled by the
                #        "compute the vectors for this file" method, above.
                if len(vector) == 0 or\
                        len([a for a in vector if a == 0]) == len(vector):
                    # Zero length vector or zeroed out vector is an indication
                    # that Marsyas choked.
                    self.computations[file_key]['failed'] = True

            self.computations[file_key]['vectors'] = results
            self.computations[file_key]['complete'] = True

        def failure(err):
            # Crap. Something threw an exception inside
            # self.generate_all_plugin_vectors
            logger.debug("Computation error :( %s")
            self.computations[file_key]['failed'] = True
            self.computations[file_key]['complete'] = True

        def remove_file(val, tmp_file_name):
            # After vectors are calculated (or not) clean up the temp file.
            os.remove(tmp_file_name)
            return val

        def downloaded_file(tmp_file_name):
            logger.debug("Finished downloading %s as %r", file_uri, tmp_file_name)

            self.computations[file_key]['downloaded'] = True
            # Set up a deferred that will return a dict of plugin vectors
            df = self.generate_all_plugin_vectors(tmp_file_name, file_key)
            # Set up our success and failure methods
            df.addCallback(got_vectors)
            df.addErrback(failure)
            df.addBoth(remove_file, tmp_file_name)

        def download_file():
            # Receive the file in the main loop, but spin processing off
            # into its own thread.
            logger.debug("Downloading http://%s:%d%s",
                    _rpcNodeContact.address,
                    _rpcNodeContact.port,
                    file_uri)
            clientFactory = protocol.HTTPClientFactory(
                    downloaded_file, file_key, file_uri, timeout=0)
            reactor.connectTCP(_rpcNodeContact.address,
                    _rpcNodeContact.port, clientFactory)

        download_file()

        return "OK"

    @rpcmethod
    def poll(self, file_key, _rpcNodeID, _rpcNodeContact, **kwargs):
        logger.debug("Returning poll")

        if not self.computations.has_key(file_key):
            # we've never heard of the requested offload operation.
            # make something up!
            logger.debug("Poll status: Never heard of that file")
            result = {'complete': True, 'vectors': None, 'failed': True, 'downloaded': False}
        else:
            result = self.computations[file_key]

            if self.computations[file_key]['complete']:
                # we've finished the requested offload operation.
                # remove if from the list and return it
                # FIXME: Deleting this here could be dangerous; if the message
                #        gets lost on the network, the requesting node won't be
                #        able to re-request the results.
                logger.debug("Poll status: Complete")
                del self.computations[file_key]
            else:
                logger.debug("Poll status: In Progress")

        return result

