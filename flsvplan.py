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

	def getRun(self):
		return self.run

	def setRun(self, run):
		self.run = run

	def showToolTip(self,title,msg,msgtype):
		self.tray.showInfo(title, msg)
		return 0
	
	def getNewFiles(self):
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
		try:
			d = urllib.urlencode(values)
			req = urllib2.Request(self.getSendURL(), d)
			response = urllib2.urlopen(req)
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

		print "This is what you want: ", str
		tmp = self.parse_table(str)
		self.showToolTip('Neuer Vertretungsplan','Es wurde eine neue Datei gefunden! Sie wird jetzt hochgeladen.','info')
		self.send_table(tmp)

	def loadConfig(self):
		self.config = ConfigParser.ConfigParser()
		self.config.read("config.ini")
	@staticmethod
	def bye(self):
		print "Auf Wiedersehen!"
		os._exit(0)
 	
	def initTray(self):
		if os.name in "nt":
			#from SysTrayIcon import SysTrayIcon
			from taskbardemo import DemoTaskbar, Taskbar
			menu = (
					('Beenden', None, Vertretungsplaner.bye),
				)
			self.tray = DemoTaskbar(self,'fls_logo.ico', 'FLS Vertretungsplaner', menu)
			#self.tray = thread.start_new_thread(DemoTaskbar, (self,'./fls_logo.ico', 'FLS Vertretungsplaner', menu))
			self.tray.showInfo('Vertretungsplaner startet...', 'Bei Problemen wenden Sie sich bitte an die Homepage AG der Friedrich-List-Schule Wiesbaden.')
			
	def __init__(self):
		self.loadConfig()
		self.initTray()
		self.initPlan()

app = Vertretungsplaner()
win32gui.PumpMessages()
