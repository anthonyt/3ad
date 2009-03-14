#!/usr/bin/env python

import wx
import sys
import time
from twisted.internet import wxreactor; wxreactor.install()
from twisted.internet import reactor
from twisted.internet import defer
import entangled.dtuple
import entangled.kademlia.contact
import entangled.kademlia.msgtypes
from entangled.kademlia.node import rpcmethod
import hashlib
import cPickle
from functools import partial


"""
Entangled depends on Twisted (py25-twisted) for network programming
Entangled depends on sqlite3 (py25-sqlite3) for the SqliteDataStore class. Could just use the DictDataStore class instead.
Twisted depends on ZopeInterface (py25-zopeinterface)
"""

class MyMenu(wx.Frame):

    panels = None

    def __init__(self, parent, id, title):
        wx.Frame.__init__(self, parent, id, title, wx.DefaultPosition, wx.Size(600, 450))

        # setup some uninitialized instance variables
        self.txt_search = None
        self.txt_tag = None
        self.lc = None
        self.displayed_files = []
        self.panels = {'buttons': wx.Panel(self, -1, style=wx.SIMPLE_BORDER),
                       'list': wx.Panel(self, -1, style=wx.SIMPLE_BORDER) }

        # setup the layout of the main panel
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        px_border = 3
        sizer.Add(self.panels['buttons'], 0, wx.EXPAND | wx.ALL, px_border)
        sizer.Add(self.panels['list'], 1, wx.EXPAND | wx.TOP | wx.RIGHT | wx.BOTTOM, px_border)
        self.SetSizer(sizer)

        # setup the individual components
        self._setupMenuBar()
        self._setupButtons(self.panels['buttons'])
        self._setupList(self.panels['list'])


        self.statusbar = self.CreateStatusBar()
        self.Centre()


    def _setupButtons(self, panel):
        px_gap2 = 20
        px_gap1 = 3

        # setup add button and top spacer
        btn_add = wx.Button(panel, 1, "Add Files to Library")
        spacer = wx.StaticText(panel, -1, '')

        # setup search elements
        pnl_search = wx.Panel(panel, -1, style=wx.SIMPLE_BORDER)
        lbl_search = wx.StaticText(pnl_search, -1, 'Search By Tag:')
        txt_search = wx.wx.TextCtrl(pnl_search, -1)
        btn_search = wx.Button(pnl_search, 2, "Search!")

        # setup sizer for search elements
        szr_search = wx.BoxSizer(wx.VERTICAL)
        szr_search.Add(lbl_search, 0, wx.ALL, px_gap1)
        szr_search.Add(txt_search, 0, wx.EXPAND | wx.ALL, px_gap1)
        szr_search.Add(btn_search, 0, wx.EXPAND | wx.ALL, px_gap1)
        pnl_search.SetSizer(szr_search)

        # setup tagging elements
        pnl_tag = wx.Panel(panel, -1, style=wx.SIMPLE_BORDER)
        lbl_tag = wx.StaticText(pnl_tag, -1, 'Tag Selected Files:')
        txt_tag = wx.wx.TextCtrl(pnl_tag, -1)
        btn_tag = wx.Button(pnl_tag, 3, "Tag!")

        # setup sizer for tagging elements
        szr_tag = wx.BoxSizer(wx.VERTICAL)
        szr_tag.Add(lbl_tag, 0, wx.ALL, px_gap1)
        szr_tag.Add(txt_tag, 0, wx.EXPAND | wx.ALL, px_gap1)
        szr_tag.Add(btn_tag, 0, wx.EXPAND | wx.ALL, px_gap1)
        pnl_tag.SetSizer(szr_tag)

        # setup sizer for the main panel
        sizer = wx.GridBagSizer(px_gap2, px_gap2)
        sizer.Add(spacer, (0,0))
        sizer.Add(btn_add, (1,0), flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(pnl_search, (2,0), flag=wx.EXPAND)
        sizer.Add(pnl_tag, (3, 0), flag=wx.EXPAND)
        sizer.Add(wx.StaticText(self, -1, ''), (3, 0), flag=wx.EXPAND)
        panel.SetSizer(sizer)

        # add some event callbacks!
        self.Bind(wx.EVT_BUTTON, self.AddFiles, id=1)
        self.Bind(wx.EVT_BUTTON, self.SearchFiles, id=2)
        self.Bind(wx.EVT_BUTTON, self.TagFiles, id=3)

        # set some instance variables
        self.txt_search = txt_search
        self.txt_tag = txt_tag

    def _setupList(self, panel):
        px_gap = 0
        sizer = wx.GridBagSizer(px_gap, px_gap)
        self.lc = wx.ListCtrl(panel, -1, style=wx.LC_REPORT)
        self.lc.InsertColumn(0, 'File Name')
        self.lc.InsertColumn(1, 'Tags')
        self.lc.InsertColumn(2, 'File Path')
        self.lc.InsertColumn(3, 'Vector')
        self.lc.SetColumnWidth(0, 200)
        self.lc.SetColumnWidth(1, 200)
        self.lc.SetColumnWidth(2, 150)
        self.lc.SetColumnWidth(3, 150)

        sizer.Add(self.lc, (0, 0), flag=wx.EXPAND)
        sizer.AddGrowableRow(0)
        sizer.AddGrowableCol(0)
        panel.SetSizer(sizer)


    def _setupMenuBar(self):
        menubar = wx.MenuBar()

        file = wx.Menu()
        edit = wx.Menu()
        help = wx.Menu()

        file.Append(101, '&Open', 'Open a new document')
        file.Append(102, '&Save', 'Save the document')
        file.AppendSeparator()

        quit = wx.MenuItem(file, 105, '&Quit\tCtrl+Q', 'Quit the Application')
        file.AppendItem(quit)

        edit.Append(201, 'check item1', '', wx.ITEM_CHECK)
        edit.Append(202, 'check item2', kind=wx.ITEM_CHECK)

        submenu = wx.Menu()
        submenu.Append(301, 'radio item1', kind=wx.ITEM_RADIO)
        submenu.Append(302, 'radio item2', kind=wx.ITEM_RADIO)
        submenu.Append(303, 'radio item3', kind=wx.ITEM_RADIO)
        edit.AppendMenu(203, 'submenu', submenu)

        menubar.Append(file, '&File')
        menubar.Append(edit, '&Edit')
        menubar.Append(help, '&Help')

        self.SetMenuBar(menubar)

        self.Bind(wx.EVT_MENU, self.OnQuit, id=105)


    def AddFiles(self, event):
        file_data = [
            (u"audio/Cello note a.wav", [u"cello", u"strings", u"a"]),
            (u"audio/Cello note c.wav", [u"cello", u"strings", u"c"]),
            (u"audio/Cello note g.wav", [u"cello", u"strings", u"g"])
#            ("audio/Cello note a.wav", []),
#            ("audio/Cello note c.wav", []),
#            ("audio/Cello note g.wav", [])
#            (str(int(time.time())), [])
        ]

        df = defer.Deferred()

        def file_added(file):
            print "--->", "added", file, file.key.encode('hex')
            return "file_added"

        def add_file(val, file_name, tags):
#            return self.controller.add_file(file_added, "/Users/anthony/Documents/school/csc466/3ad/"+file_name, tags)
            add_df = self.controller.add_file(file_added, file_name, tags)
            return add_df

        for (file_name, tags) in file_data:
            df.addCallback(add_file, file_name, tags)

        df.callback('First val')

    def SearchFiles(self, event):
        def got_files(files):
            print "->", files
            self.lc.DeleteAllItems()
            self.displayed_files = files
            self.statusbar.SetStatusText('. . . Searching . . .')

            for file in files:
                num_items = self.lc.GetItemCount()
                (dir, file_name) = os.path.split(file.file_name)
                self.lc.InsertStringItem(num_items, file_name)
                self.lc.SetStringItem(num_items, 2, dir)
                self.lc.SetStringItem(num_items, 3, str(file.vector))

                def got_tags(index, tags):
                    tagstring = ', '.join([tag.name for tag in tags])
                    self.lc.SetStringItem(index, 1, tagstring)

                self.model.get_tags(partial(got_tags, num_items), audio_file=file)

            self.statusbar.SetStatusText('Got Files!')

        taglist = self.txt_search.GetValue()
        if taglist == '':
            self.model.get_audio_files(got_files)
        else:
            tag_names = taglist.split()
            self.controller.find_files_by_tags(got_files, tag_names)


    def TagFiles(self, event):
        i = self.lc.GetFirstSelected()
        indexes = []
        while i >= 0:
            indexes.append(i)
            i = self.lc.GetNextSelected(i)

        selected_files = [self.displayed_files[i] for i in indexes]
        tag_string = self.txt_tag.GetValue()
        tag_names = tag_string.split()

        def tagged(val):
            self.SetStatusText('Tagged successfully')

        df = self.controller.tag_files(tagged, selected_files, tag_names)

    def OnQuit(self, event):
        self.Close()
        reactor.stop()
        self.Destroy()
        sys.exit(0)


class MyApp(wx.App):
    def OnInit(self):
        frame = MyMenu(None, -1, 'My Demo Program!')
        frame.Show(True)

        knownNodes = [('127.0.0.1', 5001), ('127.0.0.1', 5002)]
        udpPort = 5000

        self.node = MyNode(udpPort=udpPort)
        print "->", "joining network..."
        self.node.joinNetwork(knownNodes)
        print "->", "joined network..."
        frame.node = self.node

        nh = ad3.models.dht.NetworkHandler(self.node)
        ad3.models.dht.set_network_handler(nh)

        frame.controller = controller
        frame.model = model

        return True

class MyNode(entangled.dtuple.DistributedTupleSpacePeer):
    def sendCustomCommand(self, key, value, originalPublisherID=None, age=0):
        if originalPublisherID == None:
            originalPublisherID = self.id
        # Prepare a callback for doing "STORE" RPC calls
        def executeCustomRPCs(nodes):
            #print '        .....execStoreRPCs called'
            for contact in nodes:
                contact.custom(key, value, originalPublisherID, age)
            return nodes
        # Find k nodes closest to the key...
        df = self.iterativeFindNode(key)
        # ...and send them STORE RPCs as soon as they've been found
        df.addCallback(executeCustomRPCs)
        return df

    @rpcmethod
    def custom(self, key, value, originalPublisherID=None, age=0, **kwargs):
        print "RECEIVED A CUSTOM RPC!"
        return "OK"


import sys
import os

# ensure the main ad3 module is on the path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

import ad3
import ad3.models
import ad3.models.dht
from ad3.models.dht import AudioFile, Plugin
from ad3.learning.euclid import Euclidean
from ad3.controller import Controller

defer.setDebugging(True)

model = ad3.models.dht
euclid = Euclidean(model)
controller = Controller(model, euclid)

app = MyApp(0)

reactor.registerWxApp(app)
reactor.run()


