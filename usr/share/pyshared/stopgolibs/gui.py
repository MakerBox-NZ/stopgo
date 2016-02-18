# -*- coding: utf-8 -*-
import wx
import wx.lib.scrolledpanel
import os
import sqlite3 as sq
from datetime import datetime, date
import time
import errno
import pref
import startprompt
import about
import json
import vlc
import subprocess
from sys import platform as _plat
import sys

USE_BUFFERED_DC = True
ID_TIMER = 100

class GUI(wx.Frame):
    def __init__(self, parent, id, title, style, clargs):
        #First retrieve the screen size of the device
        self.screenSize = wx.DisplaySize()
        self.framlog = 0
        self.camset = 0
        self.prefdate = 0
        #self.screenSize = [ 786, 768 ]
        self.screenWidth = int(self.screenSize[0] / 3)
        self.screenHeight = int(self.screenSize[1] / 1.5)
        self.previous = 0
        #fontsy = wx.SystemSettings.GetFont(wx.SYS_SYSTEM_FONT).GetPixelSize()        
        wx.Frame.__init__(self, parent, id, title, size=(self.screenWidth, self.screenHeight), style=wx.DEFAULT_FRAME_STYLE)
        self.timer = wx.Timer(self, ID_TIMER)
        self.blick = 0
        self.Bind(wx.EVT_TIMER, self.OnTimer, id=ID_TIMER)
        self.clargs = clargs
        self.InitUI()

    def InitUI(self):
        '''
        Create the $APP window, but do not load a project.
        '''
        self.CreateMenuBar()
        self.BuildStatusBar()

        vbox  = wx.BoxSizer(wx.VERTICAL)
        self.panel1 = wx.Panel(self)

        self.viewport = wx.Panel(self.panel1, wx.ID_ANY, size=(self.screenWidth,self.screenHeight/2))
        self.panel1.SetBackgroundColour("#000000")
        self.panel1.Bind(wx.EVT_PAINT, self.OnPaint)
        self.viewport.SetBackgroundColour("#101010")
        #self.viewport.Bind(wx.EVT_SIZE, lambda event, args=screenHeight: self.resize_space(event,args) )
        self.hbox  = wx.BoxSizer(wx.HORIZONTAL)
        self.hbox.AddStretchSpacer(1)
        self.hbox.Add(self.viewport, proportion=0, flag=wx.ALIGN_CENTER, border=0)
        self.hbox.AddStretchSpacer(1)

        self.panel1.SetSizer(self.hbox)

        vbox.Add(self.panel1, 4, wx.EXPAND | wx.ALIGN_CENTER)

        hbox1 = wx.BoxSizer(wx.VERTICAL)
        panel2 = wx.Panel(self, size=(-1,50))
        panel2.SetBackgroundColour("#d4d4d4")
        hbox1.Add(panel2, flag=wx.RIGHT,border=8)
        btnbox = wx.BoxSizer(wx.HORIZONTAL)
        self.Refresh()
        self.panel1.Refresh()

        self.bplay = wx.Button(panel2, label='Play')
        #bstop = wx.Button(panel2, label='Stop')
        self.brec  = wx.Button(panel2, label='Capture')

        camlist = []
        if _plat.startswith('linux'):
            for item in os.listdir('/dev'):
                if item.startswith('video'):
                    camlist.append(item)
        elif _plat.startswith('darwin'):
            pass
        elif _plat.startswith('win'):
            import re
            print('enumerating cameras')
            # probe for cams
            ffproc = subprocess.Popen(['ffmpeg','-list_devices','true','-f','dshow','-i','dummy','-hide_banner'],stderr=subprocess.PIPE)
            # get a hackedtogether [list] of ffmpeg dshow output
            ffraw = ffproc.stderr.read().split(']')
            c = 0
            n = 1
            print(c)
            while (c < len(filter(lambda x:re.search(r'\ \ +\".*\"', x), ffraw))):
                additem = filter(lambda x:re.search(r'\ \ +\".*\"', x), ffraw)[0].split('"')[1]
                if additem in camlist:
                    camlist.append(additem + ' #' + str(n))
                    n = n+1
                    c = c+1
                elif not additem in camlist:
                    camlist.append(additem)
                    c = c+1
                else:
                    print('could not add enumerated item')
                    c = c+1
                #camlist.append('camera #' + str(c) )


        #print(type(camlist))#DEBUG
        camcombo = wx.ComboBox(panel2, choices=camlist, style=wx.CB_READONLY)
        camcombo.SetValue("Set Camera")
        camcombo.Bind(wx.EVT_COMBOBOX, lambda event, args=camcombo: self.OnCamSelect(event,args) )
        panel2.Refresh()
        
        btnbox.Add(self.bplay, flag=wx.ALL, border=8 )
        #btnbox.Add(bstop, flag=wx.ALL, border=8 )
        btnbox.AddStretchSpacer(1)
        btnbox.Add(self.brec, flag=wx.ALL, border=8 )
        btnbox.AddStretchSpacer(1)
        btnbox.Add(camcombo, flag=wx.TOP,border=12)

        panel2.SetSizer(btnbox)
        hbox1.Add(btnbox, flag=wx.EXPAND, border=0)
        vbox.Add(panel2, 0, wx.EXPAND)

        self.hbox2 = wx.BoxSizer(wx.HORIZONTAL)
        self.panel3 = wx.lib.scrolledpanel.ScrolledPanel(self)
        vbox.Add(self.panel3, 1, wx.EXPAND)

        self.panel3.SetupScrolling()
        self.panel3.SetSizer( self.hbox2 )

        self.SetAutoLayout(True)
        self.SetSizer(vbox)
        self.Layout()

        #instatiate VLC
        self.Instance = vlc.Instance()
        self.player = self.Instance.media_player_new()

        #gather prefs
        self.PrefProbe()

        #if stopgo was started pointing at a project
        if self.clargs['project']:
            startprompt.Choice(self,-1)
        else:
            self.WorkSpace(False)
            print('DEBUG: project name was provided from shell')


    def CreateMenuBar(self):
        menubar = wx.MenuBar()
        fileMenu = wx.Menu()
        nitem = fileMenu.Append(wx.ID_NEW, '&New', 'New project')
        oitem = fileMenu.Append(wx.ID_OPEN, '&Open', 'Open project')
        self.ritem = fileMenu.Append(wx.ID_SAVEAS, '&Render\tCtrl-r', 'Render')
        self.qitem = fileMenu.Append(wx.ID_EXIT, '&Quit', 'Quit application')



        editMenu = wx.Menu()
        self.zitem = editMenu.Append(wx.ID_UNDO, '&Undo\tCtrl-z', 'Undo Delete')
        #yitem = editMenu.Append(wx.ID_REDO, '&Redo', 'Redo')
        self.ditem = editMenu.Append(wx.ID_DELETE, '&Delete\tDelete', 'Delete')
        pitem = editMenu.Append(wx.ID_PREFERENCES, '&Preferences\tCtrl-,', 'Preferences')

        helpMenu = wx.Menu()
        aitem = helpMenu.Append(wx.ID_ABOUT, '&About\tCtrl-?', 'About Stopgo')

        menubar.Append(fileMenu, '&File')
        menubar.Append(editMenu, '&Edit')
        menubar.Append(helpMenu, '&Help')

        self.Bind(wx.EVT_MENU, lambda event, args=(False): self.OpenFile(event,args), oitem)
        self.Bind(wx.EVT_MENU, self.NewFile, nitem)
        self.Bind(wx.EVT_MENU, self.Pref, pitem)
        self.Bind(wx.EVT_MENU, self.SimpleQuit, self.qitem)
        self.Bind(wx.EVT_CLOSE, self.SimpleQuit, self.qitem)
        self.Bind(wx.EVT_MENU, self.About, aitem)
        self.SetMenuBar(menubar)


    def BuildStatusBar(self):

        sb = self.CreateStatusBar(2)
        sb.SetStatusWidths([-3, -1])
        sb.SetStatusText("Ready")

    def BindKeys(self,dbfile):

        self.Bind(wx.EVT_MENU, lambda event, args=('wx.WXK_BACK',dbfile): self.OnKeyDown(event,args), self.ditem)
        self.Bind(wx.EVT_MENU, lambda event, args=dbfile: self.Undo(event,args), self.zitem)
        self.Bind(wx.EVT_BUTTON, lambda event, args=('wx.WXK_SPACE',dbfile): self.OnKeyDown(event,args), self.bplay)
        self.Bind(wx.EVT_BUTTON, lambda event, args=(dbfile): self.CaptureCanvas(event,args), self.brec)

        self.panel3.Bind(wx.EVT_KEY_DOWN, lambda event, args=(dbfile): self.OnKeyDown(event, args))
        self.Bind(wx.EVT_MENU, lambda event, args=(dbfile):self.OnQuit(event,args), self.qitem)
        self.Bind(wx.EVT_CLOSE, lambda event, args=(dbfile):self.OnQuit(event,args), self.qitem)
        self.Bind(wx.EVT_MENU, lambda event, args=(dbfile): self.OnRender(event,args), self.ritem)

    def WorkSpace(self,e ):
        '''
        Load in a project.
        '''

        dbfile = self.clargs['project']
        #print("you request", dbfile)

        if not os.path.isfile(dbfile):
            dlg = wx.MessageDialog(self, 'Project not found. Browse for the file?', 
                '',wx.YES_NO | wx.YES_DEFAULT 
                | wx.CANCEL | wx.ICON_QUESTION)

            val = dlg.ShowModal()

            if val == wx.ID_YES:
                self.OpenFile(e,False)
                
            elif val == wx.ID_CANCEL:
                dlg.Destroy()

        else:
            self.OpenFile(False,dbfile)


        #update timeline view
        self.Layout()
        self.panel3.SetFocus()


    def OnCamSelect(self,e,camcombo):
        self.player.stop()
        self.camhero = camcombo.GetCurrentSelection()
        #print(self.camhero)#DEBUG
        self.camset = 1

        if _plat.startswith('linux'):
            self.Media = self.Instance.media_new('v4l2:///dev/video' + str(self.camhero))
        elif _plat.startswith('darwin'):
            pass
        elif _plat.startswith('win'):
            #print(self.camhero)#DEBUG
            #self.Media = self.Instance.media_new("dshow:// #" + str(self.camhero))
            self.Media = self.Instance.media_new(u"dshow:// :dshow-vdev=" + unicode(camcombo.GetStringSelection()) + " :dshow-adev=none")

        self.player.set_media(self.Media)


        if _plat.startswith('linux'):
            self.player.set_xwindow(self.viewport.GetHandle())
        elif _plat.startswith('darwin'):
            pass
        elif _plat.startswith('win'):
            self.player.set_hwnd(self.viewport.GetHandle())

        self.player.play()


    def NewFile(self,e):

        wcd='All files(*)|*'
        directory = os.getcwd()
        dest = 'stopgo_project_'
        destid = int(time.time())
        
        sd = wx.FileDialog(self, message='Save file as...', 
            defaultDir=directory, defaultFile='stopgo_project_' + str(destid),
            wildcard=wcd, 
            style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT)

        if sd.ShowModal() == wx.ID_OK:
            projnam = sd.GetFilename()
            projpath= os.path.join(sd.GetPath(),projnam)

            # make the directory 
            # the OS does this for us but just in case..
            #if not os.path.exists( os.path.dirname(projpath) ):
                #os.makedirs( os.path.dirname(projpath))
            # make image dir
            os.makedirs( os.path.join(os.path.dirname(projpath),'images'))


        dbfile = projpath
        self.imgdir = os.path.join(os.path.dirname(projpath), 'images')
        #print(dbfile)
        #print(projpath)
        #print(self.imgdir)
        self.con = sq.connect(dbfile, isolation_level=None )

        self.cur = self.con.cursor()
        self.cur.execute("CREATE TABLE IF NOT EXISTS Project(Id INTEGER PRIMARY KEY, Path TEXT, Name TEXT, [timestamp] timestamp)")
        self.cur.execute("CREATE TABLE IF NOT EXISTS Timeline(Id INTEGER PRIMARY KEY, Image TEXT, Blackspot INT)")
        self.cur.execute("INSERT INTO Project(Path, Name, timestamp) VALUES (?,?,?)", ("images", "StopGo Project", datetime.now() ))
        #self.con.close()
        self.BindKeys(dbfile)

        sb = self.GetStatusBar()
        stat = os.path.basename(projpath) + ' created'
        sb.SetStatusText(stat, 0)
        sb.SetStatusText('', 1)
        sd.Destroy()


    def BuildTimeline(self,dbfile):

        for child in self.panel3.GetChildren():
            #print(child)#DEBUG
            child.Destroy()

        # the last frame is
        latestfram = self.cur.execute("SELECT * FROM Timeline ORDER BY Image DESC LIMIT 1")
        #latestfram = cur.execute("SELECT * FROM Timeline WHERE ID = (SELECT MAX(ID) FROM TABLE) AND Blackspot = 0");
        for entry in latestfram:
            self.framlog = int(entry[1].split('.')[0])
            self.framlog += 1
            # print(self.framlog) #DEBUG

        # timeline contains
        tbl_timeline = self.cur.execute("SELECT * FROM Timeline WHERE Blackspot=0")

        for entry in tbl_timeline:
            img = self.MakeThumbnail(os.path.join(self.imgdir, entry[1]), 100)
            self.imageCtrl = wx.StaticBitmap(self.panel3, wx.ID_ANY, 
                                             wx.BitmapFromImage(img),name=entry[1]) 
            self.imageCtrl.SetBitmap(wx.BitmapFromImage(img))
            self.imageCtrl.Bind( wx.EVT_LEFT_DOWN, self.OnLeftClick )
            self.imageCtrl.Bind( wx.EVT_LEFT_UP, self.OnLeftRelease )

            #print(self.imageCtrl.GetId())#DEBUG
            self.hbox2.Add( self.imageCtrl, 0, wx.ALL, 5 )

        self.Layout()
        self.panel3.SetFocus()
        self.BindKeys(dbfile)

        self.hbox2.Layout()
        self.panel3.Refresh()
        self.panel3.Update()

        self.Refresh()
        '''
        # TODO: this sorta converts a dir of images to a timeline
        for counter, item in enumerate( sorted(os.listdir('images')) ):
            cur.execute("INSERT INTO Project(Path, Name, timestamp) VALUES (?,?,?)", ("images", "Default Project", datetime.now() ))
            cur.execute("INSERT INTO Project(Path, Name, timestamp) VALUES (?,?,?)", ("images", "Default Project", datetime.now() ))
            cur.execute('INSERT INTO Timeline VALUES(?,?,?)', (counter,item,0))
        # TODO: if a sequence of DSC000X.JPG or whatever is provided
        # then adapt project to use DSC000X as prefix for our snapshots

        '''

    def OpenFile(self,e,filename):

        if not filename:
            wcd = 'All files (*)|*|StopGo files (*.db)|*.db'

            dirname = os.getcwd()

            od = wx.FileDialog(self, message='Choose a file', 
                               defaultDir=os.path.expanduser('~'), defaultFile='', 
                wildcard=wcd, style=wx.FD_OPEN|wx.FD_CHANGE_DIR)

            if od.ShowModal() == wx.ID_OK:
                dbfile = od.GetPath()
                self.imgdir = os.path.join( os.path.dirname( od.GetPath()),'images')

        else:
            dbfile = filename
            self.imgdir = os.path.join( os.path.dirname(filename),'images')
            #print("your image dir is ", self.imgdir )#DEBUG

        self.con = sq.connect(dbfile, isolation_level=None )

        try:
            self.cur = self.con.cursor()
            
            try: #is this a stopgo project file
                self.cur.execute("UPDATE Project SET timestamp=? WHERE Path=?", (datetime.now(),"images"))
            except:
                dlg = wx.MessageDialog(self, 'Invalid StopGo Project file. Try to open a different one?', 
                                       '',wx.OK | wx.CANCEL | wx.ICON_ERROR)

                val = dlg.ShowModal()

                if val == wx.ID_OK:
                    self.OpenFile(e,False)

                elif val == wx.ID_CANCEL:
                    dlg.Destroy()

            sb = self.GetStatusBar()
            stat = os.path.basename(dbfile) + ' opened'
            sb.SetStatusText(stat, 0)
            sb.SetStatusText('', 1)

        except IOError, error:
                
            dlg = wx.MessageDialog(self, 'Error opening file\n' + str(error))
            dlg.ShowModal()
            dlg.Destroy()

        except UnicodeDecodeError, error:
                
            dlg = wx.MessageDialog(self, 'Error opening file\n' + str(error))
            dlg.ShowModal()
            dlg.Destroy()
                
        try:
            od.Destroy()            
        except:
            pass

        self.BuildTimeline(dbfile)

    def MakeThumbnail(self, filepath, PhotoMaxSize):
        img = wx.Image(filepath, wx.BITMAP_TYPE_ANY)
        # scale image, preserve aspect ratio
        W = img.GetWidth()
        H = img.GetHeight()
        if W > H:
            NewW = PhotoMaxSize
            NewH = PhotoMaxSize * H / W
        else:
            NewH = PhotoMaxSize
            NewW = PhotoMaxSize * W / H
        img = img.Scale(NewW,NewH)
        return img


    def OnLeftClick(self,e):

        # give colour back to old selection
        try:
            img = self.MakeThumbnail(os.path.join(self.imgdir, self.selected.GetName() ), 100)
            self.selected.SetBitmap(wx.BitmapFromImage(img) )
        except:
            pass

        # get new selection 
        self.selected = e.GetEventObject()

        # desaturate new selection
        img = self.MakeThumbnail(os.path.join(self.imgdir, self.selected.GetName() ), 100)
        self.selected.SetBitmap(wx.BitmapFromImage(img.ConvertToGreyscale()))

        self.startdrag = self.panel3.ScreenToClient( wx.GetMousePosition() )[0]
        self.origin = self.panel3.ScreenToClient( self.selected.GetPositionTuple() )[0]
        #print(self.startdrag)


    def OnLeftRelease( self,e):

        self.player.stop()
        enddrag       = self.panel3.ScreenToClient( wx.GetMousePosition() )[0]
        diff          = enddrag-self.startdrag

        if diff == 0:
            if self.selected.GetId() == self.previous:
                img = self.MakeThumbnail(os.path.join(self.imgdir, self.selected.GetName() ), 100)
                self.selected.SetBitmap(wx.BitmapFromImage(img) )
                self.player.play()
            else:
                img = self.MakeThumbnail(os.path.join( self.imgdir, self.selected.GetName() ), self.screenHeight)
                self.GetStatusBar().SetStatusText(self.selected.GetName(), 0)
                self.PaintCanvas(img)
        elif diff > 0:
            pass
            #TODO: drag and drop reordering of frames
            #print( selected.GetName() )
            #print("mouse started at ", self.startdrag)
            #print("mouse ended at ", enddrag)
            #print("diff ", enddrag - self.startdrag )
        elif diff < 0:
            pass
            #TODO: drag and drop reordering of frames
            #print("MOVE LEFT")
            #print("mouse started at ", self.startdrag)
            #print("mouse ended at ", enddrag)
            #print("diff ", enddrag - self.startdrag )

        self.previous = self.selected.GetId()
        self.viewport.Refresh()

    def OnPaint(self, event):

        if _plat.startswith('linux'):
            dc = wx.PaintDC(self)
            dc.Clear()
        elif _plat.startswith('darwin'):
            pass
        elif _plat.startswith('win'):
            if USE_BUFFERED_DC:
                dc = wx.BufferedPaintDC(self, self._Buffer)
            else:
                dc = wx.PaintDC(self)
                dc.DrawBitmap(self._Buffer, 0, 0)
                dc.Clear()


    def OnionSkin(self,img):
        #print('onion skin') #DEBUG

        try:
            self.player.video_set_marquee_int(vlc.VideoMarqueeOption.Enable, 1)
            self.player.video_set_logo_int(vlc.VideoLogoOption.enable, 1)
            self.player.video_set_logo_string(vlc.VideoLogoOption.file, img)
            #self.player.video_set_logo_string(vlc.VideoLogoOption.file, os.path.join(os.getcwd(),'gnu.png'))
            self.player.video_set_logo_int(vlc.VideoLogoOption.delay, 0)
            self.player.video_set_logo_int(vlc.VideoLogoOption.logo_x, 10)
            self.player.video_set_logo_int(vlc.VideoLogoOption.logo_y, 10)
            self.player.video_set_logo_int(vlc.VideoLogoOption.opacity, 84)
            self.player.video_set_logo_int(vlc.VideoLogoOption.position, 100)
            self.player.video_set_logo_int(vlc.VideoLogoOption.repeat, 1)
        except:
            print('NO THAT DID NOT WORK!!')


    def PaintCanvas(self,img):
        bmp    = wx.BitmapFromImage( img )
        canvas = wx.StaticBitmap( self.viewport, bitmap=bmp, pos=(0,0) )


    def CaptureCanvas(self,e,args):
        #print('CAPTURE')#DEBUG
        if self.camset == 1:
            self.framlog += 1
            #print(self.camhero)#DEBUG
            vidcap = vlc.libvlc_video_take_snapshot(self.player, 0, os.path.join(self.imgdir, str(self.framlog).zfill(3)+'.png'), 0,0)
            self.cur.execute('INSERT INTO Timeline VALUES(Null,?,?)', (str(self.framlog).zfill(3)+'.png',0))

            # add graphically to timeline
            img = self.MakeThumbnail(os.path.join(self.imgdir, str(self.framlog).zfill(3)+'.png'), 100)
            self.imageCtrl = wx.StaticBitmap(self.panel3, wx.ID_ANY, wx.BitmapFromImage(img),name=str(self.framlog).zfill(3)+'.png') 
            self.imageCtrl.SetBitmap(wx.BitmapFromImage(img))
            self.imageCtrl.Bind( wx.EVT_LEFT_DOWN, self.OnLeftClick )
            self.imageCtrl.Bind( wx.EVT_LEFT_UP, self.OnLeftRelease )
            #print(self.imageCtrl.GetId())#DEBUG
            self.hbox2.Add( self.imageCtrl, 0, wx.ALL, 5 )

            # scroll right 100% to get close to new frame
            self.panel3.Scroll(100,0)
            self.Layout()
            # draw new frame
            self.hbox2.Layout()
            self.panel3.Refresh()
            # scroll WAY right again to show frame
            self.panel3.Scroll(200,0)
            # send the shot to onion skin
            img = os.path.join(self.imgdir, str(self.framlog).zfill(3)+'.png')
            self.OnionSkin(img)

        else:
            dlg = wx.MessageDialog(self, 'Please select your camera first.','',wx.OK | wx.ICON_ERROR)
            val = dlg.ShowModal()
            if val == wx.ID_OK:
                dlg.Destroy()
            if val == wx.ID_CANCEL:
                dlg.Destroy()

    def SimpleQuit(self,e):
        '''
        If not project is open, just quit.
        '''
        self.player.stop()#windows?
        self.Close()#linux
        sys.exit()#windows

    def OnQuit(self,event,dbfile):
        if _plat.startswith('linux'):
            dlg = wx.MessageDialog(self, 'Really quit?','', wx.OK | wx.CANCEL | wx.ICON_ERROR)
            val = dlg.ShowModal()
            dlg.Show()

            if val == wx.ID_CANCEL:
                dlg.Destroy()
            elif val == wx.ID_OK:
                OKQuit = self.DBQuit(dbfile)
                if OKQuit == 42:
                    self.Close()

        elif _plat.startswith('darwin'):
            pass
        elif _plat.startswith('win'):
            OKQuit = self.DBQuit(dbfile)
            if OKQuit == 42:
                self.Close()
                sys.exit()#windows


        self.Refresh()


    def OnRender(self,e,dbfile):

        self.PrefProbe()

        self.previous = 0
        wcd='All files(*)|*'
        directory = os.getcwd()
        dest = 'stopgo-render_'
        destid = int(time.time())

        sd = wx.FileDialog(self, message='Render file as...', 
            defaultDir=directory, defaultFile=dest + str(destid) + '.mp4',
            wildcard=wcd, 
            style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT)

        if sd.ShowModal() == wx.ID_OK:
            sc_out = sd.GetPath()

        sd.Destroy()

        GoRender = self.DBQuit(dbfile)
        if GoRender == 42:
            sb = self.GetStatusBar()
            dlg = wx.MessageDialog(self,'Rendering complete.','',wx.OK|wx.ICON_INFORMATION)
            sb.SetBackgroundColour("#d11")
            sb.SetStatusText('Rendering...', 0)
            sb.Refresh()

            self.sc_command = 'ffmpeg'

            if _plat.startswith('linux'):
                P = subprocess.Popen(self.sc_command + " -r "+self.sc_fps+" -pattern_type glob -i '*.png' -b:v "+self.sc_bit+" -s " + self.sc_size + " -acodec NULL -y "+sc_out, cwd=self.imgdir, shell=True)
                
            elif _plat.startswith('darwin'):
                    pass

            elif _plat.startswith('win'):
                stnum  = int(os.listdir(self.imgdir)[0].split('.')[0])
                aratio = int(''.join(n for n in self.sc_size if n.isdigit()))
                P = subprocess.Popen(self.sc_command +' -f image2 -start_number ' + str(stnum) + ' -r '+self.sc_fps+' -s '+self.sc_size+' -i \"' + self.imgdir + '\%03d.png\" -b:v '+self.sc_bit+' -vf scale='+str(aratio)+':-1 -aspect 16:9 -acodec NULL -y '+sc_out, cwd=self.imgdir, shell=True)



            output = P.communicate()[0]
            print(P.returncode," Rendering complete!")

            while True:
                val = dlg.ShowModal()
                if val == wx.ID_OK:
                    sb.SetStatusText('Ready.', 0)
                    sb.SetBackgroundColour("#eee")
                    sb.Refresh()
                    break

            dlg.Destroy()

        else:
            print('WIN CONFUSION')
            '''
            # windows config not implemented yet
            self.myprefs = 'winconfuse'
            dlg = wx.MessageDialog(self, "Render on Windows not yet supported. For now, render on Linux (it's free).", '',wx.OK | wx.ICON_ERROR)
            val = dlg.ShowModal()
            if val == wx.ID_YES:
                dlg.Destroy()
            '''

    def onBusy(self,msf):
        # implement a better gauge of render time
        #proggy.Tormato(self,-1)
        pass

    def DBQuit(self,dbfile):
        self.cur = self.con.cursor()
        self.cur.execute("SELECT Image FROM Timeline WHERE Blackspot==1")

        blacklist = self.cur.fetchall()

        for blackitem in blacklist:
            os.remove(os.path.join(self.imgdir,blackitem[0]) )

        self.cur.execute("DELETE FROM Timeline WHERE Blackspot=1")
        self.con.commit()
        #self.con.close()

        return 42


    def OnKeyDown(self, e, args):
        #print('args --->', args)#DEBUG
        if len(args) == 2:
            key = args[0]
            dbfile = args[1]
        else:
            key = e.GetKeyCode()
            dbfile = args
            #print(dbfile)#DEBUG

        if  key==wx.WXK_ESCAPE:
            #print("ESCAPE", self.selected.GetName() )
            pass
        # delete
        elif key==wx.WXK_BACK or key=='wx.WXK_BACK':
            try:
                self.cur.execute("UPDATE Timeline SET Blackspot=? WHERE Image=?", (1, self.selected.GetName() )) 
                self.cur.execute("SELECT * FROM Timeline WHERE Blackspot=1")
                self.lastdel = self.selected.GetName()
                #print(cur.fetchall())#DEBUG
                self.con.commit()

                self.selected.Destroy()
                self.panel3.Freeze()
                self.hbox2.Layout()
                self.panel3.Refresh()
                self.panel3.Update()
                self.panel3.Thaw()

            except:
                #print("Nope, nothing is selected.")#DEBUG
                pass

        # play
        elif key==wx.WXK_SPACE or key=='wx.WXK_SPACE':
            self.PrefProbe()
            if self.prefdate == 1:
                self.timer.Start(1000/int(self.sc_fps))
            else:
                self.timer.Start(1000/8)

            self.previous = 0
            img = self.MakeThumbnail(os.path.join(self.imgdir, self.selected.GetName() ), 100)
            self.selected.SetBitmap(wx.BitmapFromImage(img) )

            self.cur.execute("SELECT * FROM Timeline WHERE Blackspot==0")
            self.framlist = self.cur.fetchall()

        #e.Skip()


    def OnTimer(self,e):
        try:
            filepath = os.path.join(self.imgdir,self.framlist[self.blick][1])
            img = self.MakeThumbnail(filepath, 640)
            self.PaintCanvas(img)
            self.blick = self.blick + 1
            #print(self.blick)#DEBUG
        except:
            #print('Timer Fail')#DEBUG
            self.timer.Stop()
            self.blick = 0
            self.player.play()


    def About(self,e):
        about.OnAboutBox(self)

    def Pref(self,e):
        #print('prefs')
        self.PrefProbe()
        pref.GUIPref(None, -1, 'Stopgo Preferences', (self.screenWidth, self.screenHeight), wx.DEFAULT_FRAME_STYLE)
        self.prefdate = 1


    def Undo(self,e,dbfile):
        sb = self.GetStatusBar()

        try:
            self.cur.execute("UPDATE Timeline SET Blackspot=? WHERE Image=?", (0, self.lastdel )) 
            #print(cur.fetchone())#DEBUG
            self.con.commit()
            sb.SetStatusText('Undo successful', 0)
        except:
            sb.SetStatusText('Cannot Undo', 0)

        self.BuildTimeline(dbfile)

    def PrefProbe(self):
        # on windows this path may not exist
        if not os.path.exists(os.path.join(os.path.expanduser("~"), '.config')):
            os.makedirs( os.path.join(os.path.expanduser("~"), '.config'))
        else:
            pass

        # does config file exist
        if not os.path.isfile(os.path.join(os.path.expanduser("~"),'.config','stopgo.conf.json')):
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
            defpref = '{"profile": "1080p", "bitrate": "21Mbps", "fps": "8", "encoder": "ffmpeg"}'
            file_handle = os.open(os.path.join(os.path.expanduser("~"),'.config','stopgo.conf.json'), flags)
            with os.fdopen(file_handle, 'w') as file_obj:
                file_obj.write(defpref)
                file_obj.close()
        else:
            #it already exists
            pass

        dosiero = open(os.path.join(os.path.expanduser("~"), '.config', 'stopgo.conf.json'), 'r')
        self.myprefs = json.load(dosiero)
        self.sc_command = self.myprefs['encoder']

        self.sc_fps     = self.myprefs['fps']

        if self.myprefs['profile'] == '1080p':
            self.sc_size = 'hd1080'
        elif self.myprefs['profile'] == '720p':
            self.sc_size = 'hd720'

        if self.myprefs['bitrate'] == '7Mbps':
            self.sc_bit = '7000k'
        elif self.myprefs['bitrate'] == '14Mbps':
            self.sc_bit = '14000k'
        else:
            self.sc_bit = '21000k'


    def UndoHistory(self,e):
        # TODO: accidentally removed frames?
        # use this UNDO function to create window listing all BLACKSPOT frames
        # restore them from that window
        pass


def main(opts):
    app = wx.App(False)
    window = GUI(None, id=1, title="stopgo", style=wx.DEFAULT_FRAME_STYLE | wx.FULL_REPAINT_ON_RESIZE, clargs=opts)
    window.Show()
    app.MainLoop()
    return True