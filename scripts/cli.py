#!/usr/bin/env python
import os
import sys
import time
import hashlib
import cPickle
from twisted.internet import selectreactor; selectreactor.install()
from twisted.internet import reactor
from twisted.internet import defer
from functools import partial

# ensure the main ad3 module is on the path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
        sys.path.append(parent_dir)

        import ad3
        import ad3.models
        import ad3.models.dht
        from ad3.models.dht import AudioFile, Plugin
        from ad3.learning import *
        from ad3.learning.euclid import Euclidean
        from ad3.learning.gauss import Gaussian
        from ad3.learning.svm import SVM
        from ad3.controller import Controller

        defer.setDebugging(True)

# Our Model
model = ad3.models.dht

# Our classifiers
euclidean = Euclidean(model)
gaussian = Gaussian(model, 100)
svm = SVM(model)

# Our controller
controller = Controller(model, svm)

# Our User
user_name = sys.argv[2]
knownNodes = [('24.68.144.235', 4002)]
knownNodes = [('127.0.0.1', 4000)]
udpPort = int(sys.argv[1])
node = ad3.models.dht.MyNode(udpPort=udpPort)
print "->", "joining network..."
node.joinNetwork(knownNodes)
print "->", "joined network..."
nh = ad3.models.dht.NetworkHandler(node)
ad3.models.dht.set_network_handler(nh)
reactor.run()
