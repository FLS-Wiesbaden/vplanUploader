#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Module to upload standin plans.

This module is there in order to parse, figure out and uploads
standin plans for the FLS Wiesbaden framework.
"""

__all__ = []
__version__ = '4.25'
__author__ = 'Lukas Schreiner'

import urllib.request
import urllib.parse
import urllib.error
import traceback
import sys
import os
import os.path
import json
import base64
import configparser
import shutil
import pickle
from threading import Thread
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject
from PyQt5.QtGui import QIcon
from searchplaner import SearchPlaner
from errorlog import ErrorDialog
from planparser.fls import FlsCsvParser
from planparser.davinci import DavinciJsonParser

APP = None
APPQT = None

class WatchFile(object):
	"""A file which is or was watched in order to retrieve information"""

	def __init__(self, path, fname):
		self.path = path
		self.name = fname

		stInfo = os.stat(self.getFullName)
		self.mtime = stInfo.st_mtime
		self.atime = stInfo.st_atime

	@property
	def getFullName(self):
		return '%s/%s' % (self.path, self.name)

class Vertretungsplaner(QObject):
	showDlg = pyqtSignal()
	hideDlg = pyqtSignal()
	message = pyqtSignal(str, str, int, int)
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
		return self.config.has_option('options', name) and self.config.get('options', name) in ['True', True]

	def getIntervall(self):
		return float(self.config.get("default", "intervall"))

	def isProxyEnabled(self):
		return self.config.get('proxy', 'enable') == 'True' or self.config.get('proxy', 'enable') is True

	def getRun(self):
		return self.run

	def setRun(self, run):
		self.run = run

	def showInfo(self, title, msg):
		self.showToolTip(title, msg, 'info')

	def showError(self, title, msg):
		self.showToolTip(title, msg, 'error')

	def showToolTip(self, title, msg, msgtype):
		trayIcon = QSystemTrayIcon.Critical if msgtype == 'error' else QSystemTrayIcon.Information
		timeout = 10000
		self.message.emit(title, msg, trayIcon, timeout)

	@pyqtSlot()
	def getNewFiles(self):
		print('Starte suche...')

		self.locked = True
		pathToWatch = self.getWatchPath()

		try:
			after = dict([(f, WatchFile(pathToWatch, f)) for f in os.listdir(pathToWatch)])
		except FileNotFoundError:
			print('\nCould not poll directory %s (does not exist!)' % (pathToWatch,))
			# try recreate the directory (maybe it does not exist in base path:
			try:
				os.makedirs(pathToWatch)
			except:
				pass
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
		except FileNotFoundError:
			print('\nCould not poll directory %s (does not exist!)' % (pathToWatch,))
			self.before = {}

		# Now start Looping
		self.search = Thread(target=SearchPlaner, args=(self,)).start()

	def sendPlan(self, table, absFile, planType='all'):
		data = json.dumps(table).encode('utf-8')
		# check what we need to do.
		# 1st we need to save the data?
		if self.config.getboolean('options', 'saveResult'):
			destFileName = os.path.join(
				self.config.get('default', 'resultPath'),
				'vplan-result-{:s}.json'.format(datetime.now().strftime('%Y-%m-%d_%H%M%S_%f'))
			)
			if not os.path.exists(os.path.dirname(destFileName)):
				os.makedirs(os.path.dirname(destFileName))
			with open(destFileName, 'wb') as f:
				f.write('Type: {:s}\n'.format(planType).encode('utf-8'))
				f.write(data)

		if self.config.getboolean('options', 'upload'):
			data = base64.b64encode(data).decode('utf-8').replace('\n', '')
			values = {
				'apikey': base64.b64encode(self.getAPIKey().encode('utf-8')).decode('utf-8').replace('\n', ''),
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
					"http" : httpproxy,
					"https": httpproxy
				}

				opener = urllib.request.build_opener(urllib.request.ProxyHandler(proxies))
				urllib.request.install_opener(opener)

			else:
				print('Proxy is deactivated')
				opener = urllib.request.build_opener(urllib.request.HTTPHandler)
				urllib.request.install_opener(opener)

			request = urllib.request.Request(self.getSendURL(), d.encode('utf-8'))
			if self.config.has_option("siteauth", "enable") and self.config.get("siteauth", "enable") == 'True':
				authstr = base64.b64encode(
						('%s:%s' % (
							self.config.get("siteauth", "username"),
							self.config.get("siteauth", "password")
						)).encode('utf-8')
					).decode('utf-8').replace('\n', '')
				request.add_header("Authorization", "Basic %s" % authstr)

			# add post info
			request.add_header('Content-Type', 'application/x-www-form-urlencoded;charset=utf-8')

			try:
				response = opener.open(request)
				response.read()
				self.showInfo('Vertretungsplan hochgeladen', 'Die Datei wurde erfolgreich hochgeladen.')
				print('Erfolgreich hochgeladen.')
			except urllib.error.HTTPError as err:
				self.createCoreDump(err)
				self.showError(
					'Warnung',
					'Der Vertretungsplan konnte eventuell nicht korrekt hochgeladen werden. \
					Bitte kontaktieren Sie das Website-Team der FLS!'
				)
				print('HTTP-Fehler aufgetreten: {:d} - {:s}'.format(err.code, err.reason))
			except urllib.error.URLError as err:
				self.createCoreDump(err)
				self.showError(
					'Warnung',
					'Der Vertretungsplan konnte eventuell nicht korrekt hochgeladen werden. \
					Bitte kontaktieren Sie das Website-Team der FLS!'
				)
				print('URL-Fehler aufgetreten: {:s}'.format(err.reason))
			except Exception as err:
				self.createCoreDump(err)
				self.showError(
					'Warnung',
					'Der Vertretungsplan konnte eventuell nicht korrekt hochgeladen werden. \
					Bitte kontaktieren Sie das Website-Team der FLS!'
				)
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

		path = os.path.dirname(__file__) if os.path.dirname(__file__) else sys.path[0]
		if path and not os.path.isdir(path):
			path = os.path.dirname(path)
		path = '%s%scoredump' % (path, os.sep)
		filename = '%s%s%s-%s.dump' % (path, os.sep, __file__, datetime.now().strftime('%Y%m%d%H%M%S%f'))
		# truncate folder
		if os.path.exists(path):
			shutil.rmtree(path, ignore_errors=False, onerror=None)
		os.makedirs(path)

		dump = {}
		dump['tb'] = traceback.format_exc()
		dump['tbTrace'] = {}
		dump['err'] = self.dumpObject(err)
		excInfo = sys.exc_info()

		i = 0
		while i < len(excInfo):
			dump['tbTrace'][i] = 'No args available: %s' % (excInfo[i],)
			i += 1

		with open(filename, 'wb') as f:
			pickle.dump(dump, f, protocol=pickle.HIGHEST_PROTOCOL)

		print('Coredump created in %s' % (filename,))

	def dumpObject(self, obj):
		struc = {}
		for k, v in vars(obj).items():
			if not k.startswith('_') and k != 'fp':
				try:
					struc[k] = self.dumpObject(v)
				except:
					struc[k] = v

		return struc

	def moveAndDeleteVPlanFile(self, absFile):
		# file => Actual file (move to lastFile)
		# self.lastFile => last File (delete)
		path = absFile
		if os.path.exists(self.lastFile) and self.lastFile != '':
			# delete
			os.remove(self.lastFile)
			print('File %s removed' % (self.lastFile))
		# move
		newFile = ''
		if self.config.get('options', 'backupFiles') == 'True':
			newFile = "%s.backup" % (path)
			if self.config.get('options', 'backupFolder') != 'False':
				backdir = self.config.get('options', 'backupFolder')
				if backdir[-1:] is not os.sep:
					backdir = '%s%s' % (backdir, os.sep)
				newFile = '%s%s%s%s.backup' % (self.getWatchPath(), os.sep, backdir, path)
				# before: check if folder eixsts.
				backdir = '%s%s%s' % (self.getWatchPath(), os.sep, backdir)
				if not os.path.exists(backdir):
					os.makedirs(backdir)
				print('Copy %s to %s for backup.' % (path, newFile))
				shutil.copyfile(path, newFile)

		if self.config.get('options', 'delUpFile') == 'True' and os.path.exists(path):
			print('Delete uploaded file %s' % (path))
			os.remove(path)

		self.lastFile = newFile

	def handlingFlsCSV(self, fileName):
		# send a notification
		self.showInfo('Neuer Vertretungsplan', 'Es wurde eine neue Datei gefunden und wird jetzt verarbeitet.')
		absPath = os.path.join(self.config.get('default', 'path'), fileName)

		try:
			djp = FlsCsvParser(self.config, self.dlg, absPath)
			djp.planFileLoaded.connect(self.planFileLoaded)
			djp.planParserPrepared.connect(self.planParserPrepared)
			djp.loadFile()
			djp.preParse()
			djp.parse()
			djp.postParse()
			data = djp.getResult()
			self.showInfo('Neuer Vertretungsplan', 'Vertretungsplan wurde verarbeitet und wird nun hochgeladen.')
			self.sendPlan(data, absPath)
		except Exception as e:
			self.showError(
				'Neuer Vertretungsplan', 'Vertretungsplan konnte nicht verarbeitet werden, \
				weil die Datei fehlerhaft ist.'
			)
			print('Error: %s' % (str(e),))
			traceback.print_exc()
			self.dlg.addError(str(e))
			self.showDlg.emit()
			raise

		# something to show?
		if self.dlg.hasData:
			self.showDlg.emit()

	def handlingDavinciJson(self, fileName):
		# send a notification
		self.showInfo(
			'Neuer Vertretungsplan',
			'Es wurde eine neue Datei gefunden und wird jetzt verarbeitet.'
		)
		absPath = os.path.join(self.config.get('default', 'path'), fileName)

		try:
			djp = DavinciJsonParser(self.config, self.dlg, absPath)
			djp.planFileLoaded.connect(self.planFileLoaded)
			djp.planParserPrepared.connect(self.planParserPrepared)
			djp.loadFile()
			djp.preParse()
			djp.parse()
			djp.postParse()
			data = djp.getResult()
			self.showInfo('Neuer Vertretungsplan', 'Vertretungsplan wurde verarbeitet und wird nun hochgeladen.')
			self.sendPlan(data, absPath)
		except Exception as e:
			self.showError(
				'Neuer Vertretungsplan',
				'Vertretungsplan konnte nicht verarbeitet werden, weil die Datei fehlerhaft ist.'
			)
			print('Error: %s' % (str(e),))
			traceback.print_exc()
			self.dlg.addError(str(e))
			self.showDlg.emit()
			raise

		# something to show?
		if self.dlg.hasData:
			self.showDlg.emit()

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

	@pyqtSlot()
	def bye(self):
		global APPQT
		self.run = False
		sys.exit(0)

	def initTray(self):
		self.tray = QSystemTrayIcon(QIcon('logo.ico'), self)
		menu = QMenu('FLS Vertretungsplaner')
		menu.addAction('Planer hochladen', self.getNewFiles)
		menu.addAction('Beenden', self.bye)
		self.tray.setContextMenu(menu)
		self.message.connect(self.tray.showMessage)

		self.tray.show()

		self.showInfo(
			'Vertretungsplaner startet...',
			'Bei Problemen wenden Sie sich bitte an das Website-Team der Friedrich-List-Schule Wiesbaden.'
		)

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
	APPQT = QApplication(sys.argv)
	APPQT.setQuitOnLastWindowClosed(False)
	APP = Vertretungsplaner()

	sys.exit(APPQT.exec_())
