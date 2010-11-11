#!/usr/bin/env python

import wx
import sys
import time
from twisted.internet import wxreactor; wxreactor.install()
from twisted.internet import reactor
from twisted.internet import defer
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

        # setup button for adding demo data
        btn_demo = wx.Button(panel, 4, "Add Demo Data")
        btn_upd_tag = wx.Button(panel, 5, "Update Tag Vectors")
        btn_upd_guess = wx.Button(panel, 6, "Guess Tags for Files")

        # setup sizer for the main panel
        sizer = wx.GridBagSizer(px_gap2, px_gap2)
        sizer.Add(spacer, (0,0))
        sizer.Add(btn_add, (1,0), flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(pnl_search, (2,0), flag=wx.EXPAND)
        sizer.Add(pnl_tag, (3, 0), flag=wx.EXPAND)
        sizer.Add(btn_demo, (4, 0), flag=wx.EXPAND)
        sizer.Add(btn_upd_tag, (5, 0), flag=wx.EXPAND)
        sizer.Add(btn_upd_guess, (6, 0), flag=wx.EXPAND)
        panel.SetSizer(sizer)

        # add some event callbacks!
        self.Bind(wx.EVT_BUTTON, self.AddFiles, id=1)
        self.Bind(wx.EVT_BUTTON, self.SearchFiles, id=2)
        self.Bind(wx.EVT_BUTTON, self.TagFiles, id=3)
        self.Bind(wx.EVT_BUTTON, self.AddDemoData, id=4)
        self.Bind(wx.EVT_BUTTON, self.UpdateTagVectors, id=5)
        self.Bind(wx.EVT_BUTTON, self.UpdateGuessedTags, id=6)

        # set some instance variables
        self.txt_search = txt_search
        self.txt_tag = txt_tag

    def _setupList(self, panel):
        px_gap = 0
        sizer = wx.GridBagSizer(px_gap, px_gap)
        self.lc = wx.ListCtrl(panel, -1, style=wx.LC_REPORT)
        self.lc.InsertColumn(0, 'File Name')
        self.lc.InsertColumn(1, 'Tags')
        self.lc.InsertColumn(2, 'Guessed Tags')
        self.lc.InsertColumn(3, 'File Path')
        self.lc.InsertColumn(4, 'Vector')
        self.lc.SetColumnWidth(0, 200)
        self.lc.SetColumnWidth(1, 180)
        self.lc.SetColumnWidth(2, 180)
        self.lc.SetColumnWidth(3, 200)
        self.lc.SetColumnWidth(4, 400)

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
        file_dlg = wx.FileDialog(self, "Choose a file", os.getcwd(), "", "", wx.OPEN | wx.MULTIPLE)

        def file_added(result):
            (file, added) = result
            if added:
                print "--->", "added", file, file.key.encode('hex')
                return "file_added"
            else:
                print "--->", "file already exists:", file, file.key.encode('hex')
                return "file_added_false"
            print "--->", "added", file, file.key.encode('hex')

        def add_file(val, file_name, tags):
            add_df = self.controller.add_file(file_added, file_name, tags)
            return add_df

        if file_dlg.ShowModal() == wx.ID_OK:
            # get the list of selected files
            files = file_dlg.GetPaths()

            # get a list of tags for the files
            txt_dlg = wx.TextEntryDialog(self, 'Enter tags for the selected files, separated by spaces', 'Tag files')
            txt_dlg.SetValue("tags")
            if txt_dlg.ShowModal() == wx.ID_OK:
                tag_string = txt_dlg.GetValue()
                tag_names = tag_string.split()
            else:
                tag_names = []
            txt_dlg.Destroy()

            # start the adding
            df = defer.Deferred()
            for file_name in files:
                df.addCallback(add_file, file_name, tag_names)
            df.callback(None)

        file_dlg.Destroy()


    def AddDemoData(self, event):
        file_data = [
            (u"audio/Cello note a.wav", [u"cello", u"strings"]),
            (u"audio/Cello note c.wav", [u"cello", u"strings"]),
            (u"audio/Cello note g.wav", [u"cello", u"strings"]),
            (u"audio/_05 Allemanda - Partita No. 6 in E minor.m4a.wav", [u"piano"]),
            (u"audio/_06 Sonata in A Major D664.wav", [u"piano"]),
            (u"audio/_06 To Zanarkand.m4a.wav", [u"piano"]),
            (u"audio/_07 Eyes On Me.m4a.wav", [u"piano"]),
            (u"audio/_09 Sonata in A Major D664.wav", [u"piano"]),
#            ("audio/Cello note a.wav", []),
#            ("audio/Cello note c.wav", []),
#            ("audio/Cello note g.wav", [])
#            (str(int(time.time())), [])
        ]

        plugins = [
            ('charlotte', 'ad3.analysis_plugins.charlotte'),
#            ('bextract', 'ad3.analysis_plugins.bextract_plugin'),
#            ('centroid', 'ad3.analysis_plugins.centroid_plugin')
        ]

        df = defer.Deferred()

        def file_added(file):
            print "--->", "added", file, file.key.encode('hex')
            return "file_added"

        def plugin_added(plugin):
            print "--->", "added", plugin, plugin.key.encode('hex')
            return "plugin_added"

        def add_file(val, file_name, tags):
            file_name = u"/Users/anthony/Documents/school/csc466/3ad/"+file_name
            add_df = self.controller.add_file(file_added, file_name, tags)
            return add_df

        def add_plugin(val, name, module_name):
            p_df = self.controller.add_plugin(plugin_added, name, module_name)
            return p_df

        # add callbacks for adding plugins
        for (name, module_name) in plugins:
            df.addCallback(add_plugin, name, module_name)

        # add callbacks for adding files
        for (file_name, tags) in file_data:
            df.addCallback(add_file, file_name, tags)

        # start the callback chain
        df.callback('First val')

    def UpdateTagVectors(self, event):
        def updated(val):
            print "->", "Tag Vectors Updated"
        df = self.controller.update_tag_vectors(updated)

    def UpdateGuessedTags(self, event):
        def updated(val):
            print "->", "Guessed Tags Updated"
        df = self.controller.guess_tags(updated)

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
                self.lc.SetStringItem(num_items, 3, dir)
                self.lc.SetStringItem(num_items, 4, str(file.vector))

                def got_tags(index, tags):
                    tagstring = ', '.join([tag.name for tag in tags])
                    self.lc.SetStringItem(index, 1, tagstring)

                def got_guessed(index, tags):
                    tagstring = ', '.join([tag.name for tag in tags])
                    self.lc.SetStringItem(index, 2, tagstring)

                self.model.get_tags(partial(got_tags, num_items), audio_file=file)
                self.model.get_tags(partial(got_guessed, num_items), guessed_file=file)

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

        knownNodes = [('127.0.0.1', 5000), ('127.0.0.1', 5002)]
        udpPort = 5001
#        knownNodes = [('127.0.0.1', 5001), ('127.0.0.1', 5002)]
#        udpPort = 5000

        self.node = ad3.models.dht.MyNode(udpPort=udpPort)
        print "->", "joining network..."
        self.node.joinNetwork(knownNodes)
        print "->", "joined network..."
        frame.node = self.node

        nh = ad3.models.dht.NetworkHandler(self.node)
        ad3.models.dht.set_network_handler(nh)

        frame.controller = controller
        frame.model = model

        return True


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


