#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @author Lukas Schreiner
#

import urllib, urllib2, thread, time, os, json, codecs, base64, ConfigParser, win32gui
from table_parser import *
from searchplaner import *

class Vertretungsplaner():
	config = None
	tray = None
	search = None
	before = None
	locked = False
	run = True

	def getWatchPath(self):
		return self.config.get("default", "path")

	def getSendURL(self):
		return self.config.get("default", "url")
	
	def getAPIKey(self):
		return self.config.get("default", "api")

	def getStatus(self):
		return self.locked

	def getIntervall(self):
		return float(self.config.get("default", "intervall"))

	def getRun(self):
		return self.run

	def setRun(self, run):
		self.run = run

	def showToolTip(self,title,msg,msgtype):
		self.tray.showInfo(title, msg)
		return 0
	
	def getNewFiles(self):
		print 'Starte suche...'

		self.locked = True
		pathToWatch = self.getWatchPath()

		after = dict([(f, None) for f in os.listdir(pathToWatch)])
		added = [f for f in after if not f in self.before]
		removed = [f for f in self.before if not f in after]
		if added: print "Added new Files: ", ", ".join(added)
		if added: 
			for f in added: 
				f = f.strip()
				thread.start_new_thread(self.handlingPlaner, (f,""))
		if removed: print "Removed files: ", ", ".join(removed)
		self.before = after
		self.locked = False

	def initPlan(self):
		pathToWatch = self.getWatchPath()
		self.before = dict([(f, None) for f in os.listdir(pathToWatch)])

		# Now start Looping
		self.search = thread.start_new_thread(SearchPlaner, (self,))

	def parse_table(self,file):
		f = urllib.urlopen(file)
		p = TableParser()
		p.feed(f.read())
		f.close()
		del p.doc[0][:3]

		return p.doc

	def convert(self, table):
		for i,v in enumerate(table):
			for j,w in enumerate(table[i]):
				for k,x in enumerate(table[i][j]):
					table[i][j][k] = table[i][j][k].decode("iso-8859-15")
					table[i][j][k] = table[i][j][k].encode("utf-8")
	
		return table

	def send_table(self, table):
		# jau.. send it to the top url!
		table = self.convert(table)
		data = json.dumps(table)
		data = base64.encodestring(data).replace('\n', '')
		values = {'apikey': base64.encodestring(self.getAPIKey()).replace('\n', ''), 'data': data}
		d = urllib.urlencode(values)

        opener = None
        if self.config.get('proxy', 'enable'):
    		httpproxy = "http://"+self.config.get("proxy", "phost")+":"+self.config.get("proxy", "pport")
	    	proxies = {
		    		"http" : httpproxy
		    }
            
            opener = urllib2.build_opener(urllib2.ProxyHandler(proxies))
            urllib2.install_opener(opener)
        else:
            opener = urrlib2.build_opener(urllib2.HTTPHandler)
            urllib2.install_opener(opener)
        
		try:
            response = opener.open(self.getSendURL(), d)
			code = response.read()
			self.showToolTip('Vertretungsplan hochgeladen','Die Datei wurde erfolgreich hochgeladen.','info')
			print code
		except Exception, detail:
			self.showToolTip('Uploadfehler!','Die Datei konnte nicht hochgeladen werden. Bitte kontaktieren Sie die Homepage AG!','error')
			print "Err ", detail

	def handlingPlaner(self,file,empty):
		path = self.getWatchPath()
		sep = os.sep
		str = path+sep+file
		tmp = False

		print "This is what you want: ", str
		try:
			tmp = self.parse_table(str)
		except Exception, detail:
			tmp = False
			print 'Err ', detail

		if tmp != False:
			self.showToolTip('Neuer Vertretungsplan','Es wurde eine neue Datei gefunden! Sie wird jetzt hochgeladen.','info')
			self.send_table(tmp)
		else:
			print 'Datei gefunden, die keine Tabelle enthält!'

	def loadConfig(self):
		self.config = ConfigParser.ConfigParser()
		self.config.read("config.ini")

	def bye(self):
		print "Auf Wiedersehen!"
		self.tray.sayGoodbye()
		os._exit(0)
 	
	def initTray(self):
		if os.name in "nt":
			#from SysTrayIcon import SysTrayIcon
			from taskbardemo import DemoTaskbar, Taskbar
			menu = (
					('Planer hochladen', None, self.getNewFiles),
					('Beenden', None, self.bye),
				)
			self.tray = DemoTaskbar(self,'fls_logo.ico', 'FLS Vertretungsplaner', menu)
			#self.tray = thread.start_new_thread(DemoTaskbar, (self,'./fls_logo.ico', 'FLS Vertretungsplaner', menu))
			self.tray.showInfo('Vertretungsplaner startet...', 'Bei Problemen wenden Sie sich bitte an das Website-Team der Friedrich-List-Schule Wiesbaden.')
			
	def __init__(self):
		self.loadConfig()
		self.initTray()
		self.initPlan()

app = Vertretungsplaner()
win32gui.PumpMessages()
