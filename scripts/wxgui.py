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
        wx.Frame.__init__(self, parent, id, title, wx.DefaultPosition, wx.Size(600, 500))

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
        btn_upd_test = wx.Button(panel, 7, "Test Classifiers")

        # setup sizer for the main panel
        sizer = wx.GridBagSizer(px_gap2, px_gap2)
        sizer.Add(spacer, (0,0))
        sizer.Add(btn_add, (1,0), flag=wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(pnl_search, (2,0), flag=wx.EXPAND)
        sizer.Add(pnl_tag, (3, 0), flag=wx.EXPAND)
        sizer.Add(btn_demo, (4, 0), flag=wx.EXPAND)
        sizer.Add(btn_upd_tag, (5, 0), flag=wx.EXPAND)
        sizer.Add(btn_upd_guess, (6, 0), flag=wx.EXPAND)
        sizer.Add(btn_upd_test, (7, 0), flag=wx.EXPAND)
        panel.SetSizer(sizer)

        # add some event callbacks!
        self.Bind(wx.EVT_BUTTON, self.AddFiles, id=1)
        self.Bind(wx.EVT_BUTTON, self.SearchFiles, id=2)
        self.Bind(wx.EVT_BUTTON, self.TagFiles, id=3)
        self.Bind(wx.EVT_BUTTON, self.AddDemoData, id=4)
        self.Bind(wx.EVT_BUTTON, self.UpdateTagVectors, id=5)
        self.Bind(wx.EVT_BUTTON, self.UpdateGuessedTags, id=6)
        self.Bind(wx.EVT_BUTTON, self.test_classifiers, id=7)

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
        num_files = 0
        num_finished = [0]

        def done(val):
            self.statusbar.SetStatusText("All New Files Added!")

        def file_added(result):
            (file, added) = result
            if added:
                print "--->", "added", file, file.get_key().encode('hex')
                return "file_added"
            else:
                print "--->", "file already exists:", file, file.get_key().encode('hex')
                return "file_added_false"
            print "--->", "added", file, file.get_key().encode('hex')

        def add_file(file_name, tags):
            add_df = self.controller.add_file(file_added, file_name, user_name=user_name, tags=tags)
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

            num_files = len(files)

            # start the adding
            deferreds = []
            for file_name in files:
                deferreds.append(add_file(file_name, tag_names))
            df = defer.DefferedList(deferreds, consumeErrors=1)
            df.addCallback(done)
            self.statusbar.SetStatusText(". . . Adding Files . . .")

        file_dlg.Destroy()


    def AddDemoData(self, event):
        file_data = [
#            (u"old_audio/Cello note a.wav", [u"cello", u"strings"]),
#            (u"old_audio/Cello note c.wav", [u"cello", u"strings"]),
#            (u"old_audio/Cello note g.wav", [u"cello", u"strings"]),
#            (u"old_audio/MattP - Allemanda - Partita No. 6 in E minor.m4a.wav", [u"piano"]),
#            (u"old_audio/MattP - Sonata in A Major D664.wav", [u"piano"]),
#            (u"old_audio/MattP - To Zanarkand.m4a.wav", [u"piano"]),
#            (u"old_audio/MattP - Eyes On Me.m4a.wav", [u"piano"]),
#            (u"old_audio/MattP - Sonata in A Major D664.wav", [u"piano"]),
#            ("audio/Cello note a.wav", []),
#            ("audio/Cello note c.wav", []),
#            ("audio/Cello note g.wav", [])
#            (str(int(time.time())), [])
            (u"matt p/MattP - Terra's Theme.m4a.wav", [u"piano"]),
            (u"matt p/MattP - To Zanarkand.m4a.wav", [u"piano"]),
            (u"matt p/MattP - Sonata in A Major D664.wav", [u"piano"]),
            (u"matt p/MattP - Theme to Voyager.m4a.wav", [u"piano"])
        ]

        plugins = [
#            ('charlotte', 'ad3.analysis_plugins.charlotte'),
            ('bextract', 'ad3.analysis_plugins.bextract_plugin'),
#            ('centroid', 'ad3.analysis_plugins.centroid_plugin')
        ]

        def file_added(result):
            (file, added) = result
            if added:
                print "--->", "added", file, file.get_key().encode('hex')
                return "file_added"
            else:
                print "--->", "file already exists:", file, file.get_key().encode('hex')
                return "file_added_false"

        def plugin_added(plugin):
            print "--->", "added", plugin, plugin.get_key().encode('hex')
            return "plugin_added"

        def add_file(val, file_name, tags):
            file_name = u"/Users/anthony/"+file_name
            add_df = self.controller.add_file(file_added, file_name, user_name=user_name, tags=tags)
            return add_df

        def add_files(val, fs, ts):
            add_df = self.controller.add_files(fs, user_name=user_name, tags=ts)
            return add_df

        def add_plugin(val, name, module_name):
            p_df = self.controller.add_plugin(plugin_added, name, module_name)
            return p_df

        df = defer.Deferred()

        # add callbacks for adding plugins
        for (name, module_name) in plugins:
            df.addCallback(add_plugin, name, module_name)

        # add callbacks for adding files
#        for (file_name, tags) in file_data:
#            df.addCallback(add_file, file_name, tags)
        fs = [u"/Users/anthony/Documents/3ad_audio/new_audio/"+f for (f, t) in file_data]
        ts = [u"piano", u"twisted"]
        df.addCallback(add_files, fs, ts)
        def p(val):
            print "P CALLED"
            print val
            self.UpdateTagVectors(event)

        df.addCallback(p)

        # start the callback chain
        df.callback('First val')

    def UpdateTagVectors(self, event):
        def updated(val):
            print "->", "Tag Vectors Updated"
            self.statusbar.SetStatusText("Tag Vectors Updated!")
        self.statusbar.SetStatusText(". . . Updating Tag Vectors . . .")
        df = self.controller.update_tag_vectors(updated)

    def UpdateGuessedTags(self, event):
        def updated(val):
            print "->", "Guessed Tags Updated"
            self.statusbar.SetStatusText("Tags Guessed!")
        self.statusbar.SetStatusText(". . . Guessing new Tags . . .")
        df = self.controller.guess_tags(updated, user_name=user_name)

    def SearchFiles(self, event):
        def file_name_cmp(f1, f2):
            return cmp(f1.file_name, f2.file_name)

        def got_files(files):
            print "->", files
            self.lc.DeleteAllItems()
            self.displayed_files = files
            self.statusbar.SetStatusText('. . . Searching . . .')
            files = sorted(files, file_name_cmp)

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
            self.model.get_audio_files(got_files, user_name=user_name)
        else:
            tag_names = taglist.split()
            self.controller.find_files_by_tags(got_files, tag_names, user_name=user_name)


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

    def test_classifiers(self, event):
        data = [
            [1, 1, 2],
            [1, 2, 1],
            [2, 4, 6],
            [2, 5, 9],
            [2, 1, 1],
            [2, 1, 2],
            [2, 1, 9]
        ]
        in_class = [False, False, True, True, False, False, True]

#        # instantiate our classifiers
#        euclidean_distance = euclid.euclidean_distance

        # Get all instances in the class
        from numpy import copy, mean

        d1 = copy([data[i] for i in range(0, len(data)) if in_class[i]])

        # get all instances period
        d2 = copy(data)

        # Get the gaussian guesses. Give a tolerance of 100
        classifier_string = gauss.train(d1)
        guesses_g = gauss.predict(d2, classifier_string)
        print guesses_g
        guesses_g = [g < 100 for g in guesses_g]
        print "Size of classifier string:", len(classifier_string)

        # Get the SVM guesses.
        classifier_string = svm.train(d1)
        guesses_s = svm.predict(d2, classifier_string)
        print "Size of classifier string:", len(classifier_string)

        # Get the euclidean guesses. Give a tolerance of 5.
        mean_vector = mean(d1, axis=0)
        guesses_e = [euclid.euclidean_distance(d, mean_vector)<5 for d in d2]

        # Compress all answers into a single array
        answers = [[
                    in_class[i],
                    guesses_s[i],
                    guesses_g[i],
                    guesses_e[i]
                   ] for i in range(0, len(d2)) ]

        # Set up our counters for positive matches, negative matches
        s1 = [b for b in answers if b[0] is True]
        total_p = len(s1)
        svm_tp = float(len([a for a in s1 if a[1] == True]))
        gau_tp = float(len([a for a in s1 if a[2] == True]))
        euc_tp = float(len([a for a in s1 if a[3] == True]))

        s2 = [b for b in answers if b[0] is False]
        total_n = len(s2)
        svm_tn = float(len([a for a in s2 if a[1] == False]))
        gau_tn = float(len([a for a in s2 if a[2] == False]))
        euc_tn = float(len([a for a in s2 if a[3] == False]))

        # evaluate recall and specificity
        svm_recall = svm_tp/total_p
        gau_recall = gau_tp/total_p
        euc_recall = euc_tp/total_p
        svm_spec = svm_tn/total_n
        gau_spec = gau_tn/total_n
        euc_spec = euc_tn/total_n

        """
        for i in range(0, len(d2)):
            print "Actual:", answers[i][0], \
                "  SVM:", answers[i][1], \
                "  Gaussian:", answers[i][2], \
                "  Euclidean:", answers[i][3]
        """

        # Print a report
        print "SVM Recall:      ", svm_recall, "  SVM Specificity:      ", svm_spec
        print "Gaussian Recall: ", gau_recall, "  Gaussian Specificity: ", gau_spec
        print "Euclidean Recall:", euc_recall, "  Euclidean Specificity:", euc_spec





class MyApp(wx.App):
    def OnInit(self):
        frame = MyMenu(None, -1, user_name+"'s Library: 3AD Demo")
        frame.Show(True)

        knownNodes = [('24.68.144.235', 4002), ('192.168.1.142', 4003), ('127.0.0.1', 4001)]
        udpPort = int(sys.argv[1])


        self.node = ad3.models.dht.MyNode(udpPort=udpPort)#, networkProtocol=ad3.models.dht.MyProtocol)
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
from ad3.learning.gauss import Gaussian
from ad3.learning.svm import SVM
from ad3.learning import *
from ad3.controller import Controller

defer.setDebugging(True)

# Our Model
model = ad3.models.dht

# Our classifiers
euclidean = Euclidean(model)
gaussian = Gaussian(model, 80)
svm = SVM(model)

# Our controller
controller = Controller(model, gaussian)

# Our User
user_name = sys.argv[2]

app = MyApp(0)

reactor.registerWxApp(app)
reactor.run()


