#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @author Lukas Schreiner
#

import urllib, urllib2, thread, time, os, json, codecs, base64, ConfigParser, win32gui
from table_parser import *
from searchplaner import *

class Vertretungsplaner():

	def getWatchPath(self):
		return self.config.get("default", "path")

	def getSendURL(self):
		return self.config.get("default", "url")
	
	def getAPIKey(self):
		return self.config.get("default", "api")

	def getStatus(self):
		return self.locked

	def getOption(self, name):
		if self.config.has_option('options', name):
			if self.config.get('options', name) in ['True', True]:
				return True
			else:
				return False
		else:
			return False

	def getIntervall(self):
		return float(self.config.get("default", "intervall"))

	def isProxyEnabled(self):
		if self.config.get('proxy', 'enable') == 'True' or \
		self.config.get('proxy', 'enable') is True:
			return True
		else:
			return False

	def filesAreUTF8(self):
		if self.config.get('default', 'utf8') == 'True' or \
		self.config.get('default', 'utf8') is True:
			return True
		else:
			return False

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
		if added: print "\nAdded new Files: ", ", ".join(added)
		if added: 
			for f in added: 
				f = f.strip()
				thread.start_new_thread(self.handlingPlaner, (f,""))
		if removed: print "\nRemoved files: ", ", ".join(removed)
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
					if self.filesAreUTF8():
						table[i][j][k] = table[i][j][k].decode("utf-8")
					else:
						table[i][j][k] = table[i][j][k].decode("iso-8859-1")
						
					table[i][j][k] = self.replaceUmlaute(table[i][j][k])
					table[i][j][k] = table[i][j][k].encode("utf-8")
	
		return table

	def replaceUmlaute(self, data):
		#ue
		data = data.replace(unichr(252), '&uuml;')
		data = data.replace(unichr(220), '&Uuml;')

		#ae
		data = data.replace(unichr(228), '&auml;')
		data = data.replace(unichr(196), '&Auml;')

		#oe
		data = data.replace(unichr(246), '&ouml;')
		data = data.replace(unichr(214), '&Ouml;')

		#ss
		data = data.replace(unichr(223), '&szlig;')

		return data

	def send_table(self, table, file):
		# jau.. send it to the top url!
		table = self.convert(table)
		data = json.dumps(table)
		data = base64.encodestring(data).replace('\n', '')
		values = {'apikey': base64.encodestring(self.getAPIKey()).replace('\n', ''), 'data': data}
		d = urllib.urlencode(values)

		opener = None
		if self.isProxyEnabled():
			print 'Proxy is activated'
			httpproxy = "http://"+self.config.get("proxy", "phost")+":"+self.config.get("proxy", "pport")
			proxies = {
				"http" : httpproxy
			}
			
			opener = urllib2.build_opener(urllib2.ProxyHandler(proxies))
			urllib2.install_opener(opener)
			
		else:
			print 'Proxy is deactivated'
			opener = urllib2.build_opener(urllib2.HTTPHandler)
			urllib2.install_opener(opener)
			
		try:
			response = opener.open(self.getSendURL(), d)
			code = response.read()
			self.showToolTip('Vertretungsplan hochgeladen','Die Datei wurde erfolgreich hochgeladen.','info')
			# now move the file and save an backup. Also delete the older one.
			self.moveAndDeleteVPlanFile(file)

			print 'Erfolgreich hochgeladen.'
			print code
		except Exception, detail:
			self.showToolTip('Uploadfehler!','Die Datei konnte nicht hochgeladen werden. Bitte kontaktieren Sie das Website-Team der FLS!','error')
			print "Fehler aufgetreten."
			print "Err ", detail

		print 'Unknown Error ??'

	def moveAndDeleteVPlanFile(self, file):
		# file => Actual file (move to lastFile)
		# self.lastFile => last File (delete)
		if os.path.exists(file) and self.lastFile != '':
			# delete
			os.remove(self.lastFile)
			print 'Datei %s entfernt' % (self.lastFile)
		# move
		file_new = "%s.backup" % (file)
		print 'Move %s to %s for backup.' % (file, file_new)
		os.rename(file, file_new)
		
		self.lastFile = file_new

	def handlingPlaner(self,file,empty):
		path = self.getWatchPath()
		sep = os.sep
		str = path+sep+file
		tmp = False

		print "\nThis is what you want: ", str
		try:
			tmp = self.parse_table(str)
		except Exception, detail:
			tmp = False
			print 'Err ', detail

		if tmp != False:
			self.showToolTip('Neuer Vertretungsplan','Es wurde eine neue Datei gefunden! Sie wird jetzt hochgeladen.','info')
			self.send_table(tmp, file)
		else:
			print 'Datei gefunden, die keine Tabelle enthaelt!'

	def loadConfig(self):
		self.config = ConfigParser.ConfigParser()
		self.config.read("config.ini")

	def bye(self):
		print "Auf Wiedersehen!"
		self.tray.sayGoodbye()
		os._exit(0)

	def initTray(self):
		if os.name in "nt":
			from taskbardemo import DemoTaskbar, Taskbar
			menu = (
					('Planer hochladen', None, self.getNewFiles),
					('Beenden', None, self.bye),
				)
			self.tray = DemoTaskbar(self,'fls_logo.ico', 'FLS Vertretungsplaner', menu)
			self.tray.showInfo('Vertretungsplaner startet...', 'Bei Problemen wenden Sie sich bitte an das Website-Team der Friedrich-List-Schule Wiesbaden.')
			
	def __init__(self):
		self.lastFile = ''
		self.run = True
		self.config = None
		self.tray = None
		self.search = None
		self.before = None
		self.locked = False

		self.loadConfig()
		self.initTray()
		self.initPlan()

	def __destruct__(self):
		if os.path.exists(self.lastFile):
			os.remove(self.lastFile)
			self.lastFile = ''

app = Vertretungsplaner()
win32gui.PumpMessages()
