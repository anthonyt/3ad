#!/usr/bin/env python

import wx
import sys
from twisted.internet import wxreactor; wxreactor.install()
from twisted.internet import reactor
import entangled.dtuple
import entangled.kademlia.contact
import entangled.kademlia.msgtypes
from entangled.kademlia.node import rpcmethod
import hashlib


"""
Entangled depends on Twisted (py25-twisted) for network programming
Entangled depends on sqlite3 (py25-sqlite3) for the SqliteDataStore class. Could just use the DictDataStore class instead.
Twisted depends on ZopeInterface (py25-zopeinterface)
"""

class MyMenu(wx.Frame):

    panels = None

    def __init__(self, parent, id, title):
        wx.Frame.__init__(self, parent, id, title, wx.DefaultPosition, wx.Size(600, 450))

        self.panels = {'demo_buttons': wx.Panel(self, -1, style=wx.SIMPLE_BORDER),
                       'toolbar': wx.ToolBar(self, -1, style=wx.TB_HORIZONTAL | wx.RAISED_BORDER),
                       'grid': wx.Panel(self, -1, style=wx.SUNKEN_BORDER),
                       'list': wx.Panel(self, -1, style=wx.NO_BORDER) }

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        for name in self.panels:
            print "setting up panel:", name
            hbox.Add(self.panels[name], 1, wx.EXPAND | wx.ALL, 3)

        self._setupMenuBar()
        self._setupToolBar(self.panels['toolbar'])
        self._setupDemoButtons(self.panels['demo_buttons'])
        self._setupGridAndMouse(self.panels['grid'])
        self._setupList(self.panels['list'])

        self.SetSizer(hbox)

        self.statusbar = self.CreateStatusBar()
        self.Centre()

    def _setupGridAndMouse(self, panel):
        box = wx.BoxSizer(wx.VERTICAL)
        px_gap = 2
        sizer = wx.GridSizer(3, 3, px_gap, px_gap)

        cursors = [ wx.CURSOR_ARROW, wx.CURSOR_HAND, wx.CURSOR_WATCH, wx.CURSOR_SPRAYCAN, wx.CURSOR_PENCIL,
                    wx.CURSOR_CROSS, wx.CURSOR_QUESTION_ARROW, wx.CURSOR_POINT_LEFT, wx.CURSOR_SIZING]

        for i in cursors:
            subpanel = wx.Panel(panel, -1, style=wx.SIMPLE_BORDER)
            subpanel.SetCursor(wx.StockCursor(i))
            sizer.Add(subpanel, flag=wx.EXPAND)

        box.Add(sizer, 1, wx.EXPAND | wx.TOP, 5)
        panel.SetSizer(box)


    def _setupDemoButtons(self, panel):
        box = wx.BoxSizer(wx.VERTICAL)
        box.Add(wx.Button(panel, -1, "Button1"), 1)
        box.Add(wx.Button(panel, -1, "Button2"), 1)
        box.Add(wx.Button(panel, -1, "Button3"), 1)
        panel.SetSizer(box)



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

    def _setupList(self, panel):
        box = wx.BoxSizer(wx.VERTICAL)
        self.lc = wx.ListCtrl(self, -1, style=wx.LC_REPORT)
        self.lc.InsertColumn(0, 'File Name')
        self.lc.InsertColumn(1, 'Vector')
        #self.lc.SetColumnWidth(0, 140)
        #self.lc.SetColumnWidth(1, 153)
        box.Add(self.lc, 1, wx.EXPAND | wx.ALL, 3)
        panel.SetSizer(box)


    def _setupToolBar(self, toolbar):
        box = wx.BoxSizer(wx.HORIZONTAL)
        toolbar.AddSimpleTool(1, wx.Image('icons/search.png', wx.BITMAP_TYPE_PNG).ConvertToBitmap(), 'New', '')
        toolbar.AddSimpleTool(2, wx.Image('icons/comment.png', wx.BITMAP_TYPE_PNG).ConvertToBitmap(), 'Open', '')
        toolbar.AddSimpleTool(3, wx.Image('icons/removecomment.png', wx.BITMAP_TYPE_PNG).ConvertToBitmap(), 'Save', '')
        toolbar.AddSeparator()
        toolbar.AddSimpleTool(4, wx.Image('icons/webexport.png', wx.BITMAP_TYPE_PNG).ConvertToBitmap(), 'Exit', '')
        toolbar.Realize()
        box.Add(toolbar, 0, border=5)


        self.Bind(wx.EVT_TOOL, self.OnNew, id=1)
        self.Bind(wx.EVT_TOOL, self.OnOpen, id=2)
        self.Bind(wx.EVT_TOOL, self.OnSave, id=3)
        self.Bind(wx.EVT_TOOL, self.OnExit, id=4)

    def OnNew(self, event):
        self.statusbar.SetStatusText('New Command')
        self.node.custom('key', 'value')

    def OnOpen(self, event):
        self.statusbar.SetStatusText('Open Command')
        def got_files(files):
            print files
            self.lc.DeleteAllItems()
            for file in files:
                num_items = self.lc.GetItemCount()
                self.lc.InsertStringItem(num_items, file.file_name)
                self.lc.SetStringItem(num_items, 1, str(file.vector))

            self.statusbar.SetStatusText('Got Files!')

        self.model.get_audio_files(got_files)

    def OnSave(self, event):
        self.statusbar.SetStatusText('Save Command')
        def file_added(file):
            print "added", file
            print "key:", file.key
        self.controller.add_file(file_added, 'jimmy jimmerson.wav', tags=[])

    def OnExit(self, event):
        self.OnQuit(event)


    def OnQuit(self, event):
        self.Close()
        reactor.stop()
        self.Destroy()
        sys.exit(0)


class MyApp(wx.App):
    def OnInit(self):
        frame = MyMenu(None, -1, 'My Demo Program!')
        frame.Show(True)

        knownNodes = [('127.0.0.1', 5001)]
        udpPort = 5000

        self.node = MyNode(udpPort=udpPort)
        print "joining network..."
        self.node.joinNetwork(knownNodes)
        print "joined network..."
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

model = ad3.models.dht
euclid = Euclidean(model)
controller = Controller(model, euclid)

app = MyApp(0)

reactor.registerWxApp(app)
reactor.run()


