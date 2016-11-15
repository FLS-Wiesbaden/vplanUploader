#!/usr/bin/env python3
# -*- coding: utf8 -*-
#
# @author Lukas Schreiner
#

import urllib.request, urllib.parse, urllib.error, traceback, sys, re
import time, os, os.path, json, codecs, base64, configparser, shutil, csv
from searchplaner import SearchPlaner
from threading import Thread
from datetime import datetime
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject
from errorlog import ErrorDialog
from parser.davinci import DavinciJsonParser
from parser.fls import FlsCsvParser
import pickle
import traceback
import inspect
import pprint

app = None
if os.name in 'nt':
	import win32gui
elif os.name == 'posix':
	#from PyQt5 import QtGui
	#pyapp = QtGui.QApplication(sys.argv)
	pass

class WatchFile:

	def __init__(self, path, fname):
		self.path = path
		self.name = fname

		st_info = os.stat(self.getFullName)
		self.mtime = st_info.st_mtime
		self.atime = st_info.st_atime

	@property
	def getFullName(self):
		return '%s/%s' % (self.path, self.name)

class Vertretungsplaner(QObject):
	showDlg = pyqtSignal()
	hideDlg = pyqtSignal()
	cleanupDlg = pyqtSignal()

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

	def showToolTip(self, title, msg, msgtype):
		if self.tray is not None:
			self.tray.showInfo(title, msg)
		else:
			# ok.. than let us print on console
			print('[%s] %s: %s' % (msgtype, title, msg))
		return True

	def getNewFiles(self):
		print('Starte suche...')

		self.locked = True
		pathToWatch = self.getWatchPath()

		try:
			after = dict([(f, WatchFile(pathToWatch, f)) for f in os.listdir(pathToWatch)])
		except FileNotFoundError as e:
			print('\nCould not poll directory %s (does not exist!)' % (pathToWatch,))
			# try recreate the directory (maybe it does not exist in base path:
			try:
				os.makedirs(pathToWatch)
			except: pass
			self.locked = False
			return

		added = [f for f in after if not f in self.before]
		removed = [f for f in self.before if not f in after]
		same = [f for f in after if f in self.before]
		changed = [f for f in same if self.before[f].mtime != after[f].mtime]

		todo = added + changed
		if todo:
			print("\nChanged/Added new Files: ", ", ".join(todo))
			for f in todo:
				f = f.strip()
				execFound = False
				if self.config.get('vplan', 'type') == 'daVinci':
					if int(self.config.get('vplan', 'version')) == 6:
						if f.lower().endswith('.csv'):
							execFound = True
							try:
								self.handlingFlsCSV(f)
							except:
								pass
						elif f.lower().endswith('.json'):
							execFound = True
							# As we have an error dialog here, do not send in background!
							#Thread(target=self.handlingDavinciJson, args=(f,)).start()
							try:
								self.handlingDavinciJson(f)
							except:
								pass
				elif f.lower().endswith('.json') and not execFound:
					execFound = True
					Thread(target=self.handlingJson, args=(f,)).start()
				elif not execFound:
					print('"%s" will be ignored.' % (f,))

		if removed:
			print("\nRemoved files: ", ", ".join(removed))

		self.before = after
		self.locked = False

	def initPlan(self):
		pathToWatch = self.getWatchPath()
		try:
			if not os.path.exists(pathToWatch):
				os.makedirs(pathToWatch)

			self.before = dict([(f, WatchFile(pathToWatch, f)) for f in os.listdir(pathToWatch)])
		except FileNotFoundError as e:
			print('\nCould not poll directory %s (does not exist!)' % (pathToWatch,))
			self.before = {}

		# Now start Looping
		self.search = Thread(target=SearchPlaner, args=(self,)).start()

	def convert(self, table):
		for i,v in enumerate(table):
			for k,x in enumerate(v):
				if self.filesAreUTF8() and type(x).__name__ != 'str':
					table[i][k] = x.decode("utf8")
				elif type(x).__name__ != 'str':
					print(type(x).__name__)
					table[i][k] = x.decode("iso-8859-1")

		return table

	def send_table(self, table, absFile, planType = 'all', convert = True):
		# jau.. send it to the top url!
		if convert:
			table = self.convert(table)

		data = json.dumps(table).encode('utf8')
		data = base64.encodestring(data).decode('utf8').replace('\n', '')
		values = {
			'apikey': base64.encodestring(self.getAPIKey().encode('utf8')).decode('utf8').replace('\n', ''),
			'data': data,
			'type': planType
		}

		if self.getOption('debugOnline'):
			values['XDEBUG_SESSION_START'] = '1'
		
		d = urllib.parse.urlencode(values)
		opener = None
		if self.isProxyEnabled():
			print('Proxy is activated')
			httpproxy = "http://"+self.config.get("proxy", "phost")+":"+self.config.get("proxy", "pport")
			proxies = {
					"http" : httpproxy
					}

			opener = urllib.request.build_opener(urllib.request.ProxyHandler(proxies))
			urllib.request.install_opener(opener)

		else:
			print('Proxy is deactivated')
			opener = urllib.request.build_opener(urllib.request.HTTPHandler)
			urllib.request.install_opener(opener)

		request = urllib.request.Request(self.getSendURL(), d.encode('utf8'))
		if self.config.has_option("siteauth", "enable") and self.config.get("siteauth", "enable") == 'True':
			authstr = base64.encodestring(
					('%s:%s' % (
						self.config.get("siteauth", "username"),
						self.config.get("siteauth", "password")
					)).encode('utf8')
				).decode('utf8').replace('\n', '')
			request.add_header("Authorization", "Basic %s" % authstr)

		# add post info
		request.add_header('Content-Type', 'application/x-www-form-urlencoded;charset=utf-8')

		try:
			response = opener.open(request)
			code = response.read()
			self.showToolTip('Vertretungsplan hochgeladen','Die Datei wurde erfolgreich hochgeladen.','info')
			print('Erfolgreich hochgeladen.')
		except urllib.error.URLError as err:
			self.createCoreDump(err)
			self.showToolTip('Warnung','Der Vertretungsplan konnte eventuell nicht korrekt hochgeladen werden. Bitte kontaktieren Sie das Website-Team der FLS!','error')
			print("URL-Fehler aufgetreten: %s" % ( err.reason, ))
		except urllib.error.HTTPError as err:
			self.createCoreDump(err)
			self.showToolTip('Warnung','Der Vertretungsplan konnte eventuell nicht korrekt hochgeladen werden. Bitte kontaktieren Sie das Website-Team der FLS!','error')
			print("HTTP-Fehler aufgetreten: %i - %s" % ( err.code, err.reason ))
		except Exception as err:
			self.createCoreDump(err)
			self.showToolTip('Warnung','Der Vertretungsplan konnte eventuell nicht korrekt hochgeladen werden. Bitte kontaktieren Sie das Website-Team der FLS!','error')
			print("Unbekannter Fehler aufgetreten: ", err)

		# now move the file and save an backup. Also delete the older one.
		self.moveAndDeleteVPlanFile(absFile)

	def createCoreDump(self, err):
		if not self.getOption('createCoreDump'):
			return

		try:
			__file__
		except NameError:
			__file__ = 'flsvplan.py'
		
		path = os.path.dirname(__file__) if len(os.path.dirname(__file__)) > 0 else sys.path[0]
		if len(path) > 0 and not os.path.isdir(path):
			path = os.path.dirname(path)
		path = '%s%scoredump' % (path, os.sep)
		filename = '%s%s%s-%s.dump' % (path, os.sep, __file__, datetime.now().strftime('%Y%m%d%H%M%S%f'))
		# truncate folder
		if os.path.exists(path):
			shutil.rmtree(path, ignore_errors=False, onerror=None)
		os.makedirs(path)
		
		dump = {}
		#dump['url'] = err.geturl()
		#dump['code'] = err.getcode()
		#dump['info'] = err.info()
		#dump['hdrs'] = err.hdrs
		#dump['msg'] = err.msg
		dump['tb'] = traceback.format_exc()
		dump['tbTrace'] = {}
		excInfo = sys.exc_info()

		i = 0
		while i < len(excInfo):
			dump['tbTrace'][i] = 'No args available: %s' % (excInfo[i],)
			i += 1

		with open(filename, 'wb') as f:
			pickle.dump(dump, f)
			
		print('Coredump created in %s' % (filename,))

	def moveAndDeleteVPlanFile(self, absFile):
		# file => Actual file (move to lastFile)
		# self.lastFile => last File (delete)
		path = absFile
		if os.path.exists(self.lastFile) and self.lastFile != '':
			# delete
			os.remove(self.lastFile)
			print('File %s removed' % (self.lastFile))
		# move
		file_new = ''
		if self.config.get('options','backupFiles') == 'True':
			file_new = "%s.backup" % (path)
			if self.config.get('options', 'backupFolder') != 'False':
				backdir = self.config.get('options', 'backupFolder')
				if backdir[-1:] is not os.sep:
					backdir = '%s%s' % (backdir, os.sep)
				file_new = '%s%s%s%s.backup' % (self.getWatchPath(), os.sep, backdir, file)
				# before: check if folder eixsts.
				backdir = '%s%s%s' % (self.getWatchPath(), os.sep, backdir)
				if not os.path.exists(backdir):
					os.makedirs(backdir)
				print('Copy %s to %s for backup.' % (path, file_new))
				shutil.copyfile(path, file_new)

		if self.config.get('options', 'delUpFile') == 'True' and os.path.exists(path):
			print('Delete uploaded file %s' % (path))
			os.remove(path)

		self.lastFile = file_new

	def handlingFlsCSV(self, fileName):
		# send a notification
		self.showToolTip('Neuer Vertretungsplan','Es wurde eine neue Datei gefunden und wird jetzt verarbeitet.','info')
		absPath = os.path.join(self.config.get('default', 'path'), fileName)

		try:
			djp = FlsCsvParser(self.config, self.dlg, absPath)
			djp.planFileLoaded.connect(self.planFileLoaded)
			djp.planParserPrepared.connect(self.planParserPrepared)
			djp.loadFile()
			djp.preParse()
			djp.parse()
			djp.postParse()
			data  = djp.getResult()
			self.showToolTip('Neuer Vertretungsplan','Vertretungsplan wurde verarbeitet und wird nun hochgeladen.','info')
			self.send_table(data, absPath)
		except Exception as e:
			self.showToolTip('Neuer Vertretungsplan','Vertretungsplan konnte nicht verarbeitet werden, weil die Datei fehlerhaft ist.','error')
			print('Error: %s' % (str(e),))
			import traceback
			traceback.print_exc()
			self.dlg.addError(str(e))
			self.showDlg.emit()
			raise

		# something to show?
		if self.dlg.hasData:
			self.showDlg.emit()

	def handlingDavinciJson(self, fileName):
		# send a notification
		self.showToolTip('Neuer Vertretungsplan','Es wurde eine neue Datei gefunden und wird jetzt verarbeitet.','info')
		absPath = os.path.join(self.config.get('default', 'path'), fileName)

		try:
			djp = DavinciJsonParser(self.config, self.dlg, absPath)
			djp.planFileLoaded.connect(self.planFileLoaded)
			djp.planParserPrepared.connect(self.planParserPrepared)
			djp.loadFile()
			djp.preParse()
			djp.parse()
			djp.postParse()
			data  = djp.getResult()
			self.showToolTip('Neuer Vertretungsplan','Vertretungsplan wurde verarbeitet und wird nun hochgeladen.','info')
			self.send_table(data, absPath)
		except Exception as e:
			self.showToolTip('Neuer Vertretungsplan','Vertretungsplan konnte nicht verarbeitet werden, weil die Datei fehlerhaft ist.','error')
			print('Error: %s' % (str(e),))
			import traceback
			traceback.print_exc()
			self.dlg.addError(str(e))
			self.showDlg.emit()
			raise

		# something to show?
		if self.dlg.hasData:
			self.showDlg.emit()

	def handlingJson(self, fileName):
		path = self.getWatchPath()
		sep = os.sep
		absPath = path+sep+fileName

		content = None
		with open(absPath, 'rb') as f:
			content = f.read()
		try:
			if self.filesAreUTF8():
				content = content.decode('utf-8')
			else:
				content = content.decode('iso-8859-1')
		except:
			self.showToolTip('Neuer Vertretungsplan','Vertretungsplan konnte nicht verarbeitet werden, weil die Datei fehlerhaft  encodiert ist.','error')
			return None

		if content is None:
			self.showToolTip('Neuer Vertretungsplan','Vertretungsplan konnte nicht verarbeitet werden, weil die Datei keine Daten enthält.','error')
			return None

		# now decode.
		try:
			jsonDta = json.loads(content)
		except:
			self.showToolTip('Neuer Vertretungsplan','Vertretungsplan konnte nicht verarbeitet werden, weil die Datei fehlerhaft ist.','error')
			return None
		else:
			self.showToolTip('Neuer Vertretungsplan','Vertretungsplan wurde verarbeitet und wird nun hochgeladen.','info')
			self.send_table(jsonDta, absPath)

	@pyqtSlot()
	def planFileLoaded(self):
		pass

	@pyqtSlot()
	def planParserPrepared(self):
		if self.dlg.isVisible():
			self.hideDlg.emit()
		self.cleanupDlg.emit()

	def loadConfig(self):
		self.config = configparser.ConfigParser()
		self.config.read(["config.ini"], encoding='utf-8')

	def bye(self):
		print("Auf Wiedersehen!")
		self.tray.sayGoodbye()
		os._exit(0)

	def initTray(self):
		menu = (
			('Planer hochladen', None, self.getNewFiles),
			('Beenden', None, self.bye),
		)
		if os.name in "nt":
			from taskbardemo import DemoTaskbar, Taskbar	
			self.tray = DemoTaskbar(self,'fls_logo.ico', 'FLS Vertretungsplaner', menu)
		elif os.name == 'posix':
			#from linuxtaskbar import Taskbar
			#w = QtGui.QWidget()
			#self.tray = Taskbar(w, QtGui.QIcon('fls_logo.ico'), 'FLS Vertretungsplaner', menu)
			#self.tray.show()
			pass

		if self.tray is not None:
			self.tray.showInfo('Vertretungsplaner startet...', 'Bei Problemen wenden Sie sich bitte an das Website-Team der Friedrich-List-Schule Wiesbaden.')

	def getXmlRaw(self, element):
		return element.childNodes[0].wholeText

	def __init__(self):
		super().__init__()

		self.lastFile = ''
		self.run = True
		self.config = None
		self.tray = None
		self.search = None
		self.before = None
		self.locked = False

		self.loadConfig()
		self.initTray()

		debugLog = False
		try:
			debugLog = self.config.getboolean('options', 'debugLogs')
		except KeyError:
			pass
		except configparser.NoOptionError:
			pass

		self.dlg = ErrorDialog(debugLog)
		self.showDlg.connect(self.dlg.open)
		self.hideDlg.connect(self.dlg.close)
		self.cleanupDlg.connect(self.dlg.cleanup)
		self.initPlan()

if __name__ == '__main__':
	appQt = QApplication(sys.argv)
	appQt.setQuitOnLastWindowClosed(False)
	app = Vertretungsplaner()

	if os.name in 'nt':
		win32gui.PumpMessages()

	sys.exit(appQt.exec_())
