#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Module to upload standin plans.

This module is there in order to parse, figure out and uploads
standin plans for the FLS Wiesbaden framework.
"""

__all__ = []
__version__ = '4.37-alpha.0'
__author__ = 'Lukas Schreiner'

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
import requests
import glob
from requests.auth import HTTPBasicAuth
from threading import Thread
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject
from PyQt5.QtGui import QIcon
from searchplaner import SearchPlaner
from errorlog import ErrorDialog
from planparser import getParser
from planparser.untis import Parser as UntisParser
import sentry_sdk

# absolute hack, but required for cx_Freeze to work properly.
if sys.platform == 'win32':
	import PyQt5.sip

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
		return self.config.getboolean('proxy', 'enable', fallback=False)

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

	def getHandler(self, fileName):
		extension = os.path.splitext(fileName)[-1].lower()
		ptype = self.config.get('vplan', 'type')
		return getParser(extension, self.config)

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
				handler = self.getHandler(f)
				
				if handler:
					transName = '{}_{}_{}'.format(
						datetime.now().strftime('%Y-%m-%dT%H%M%S'),
						self.config.get('sentry', 'transPrefix', fallback='n'),
						f.replace(' ', '_')
					)
					with sentry_sdk.start_transaction(op='parseUploadPlan', name=transName) as transaction:
						try:
							self.parsePlanByHandler(transaction, handler, f)
						except Exception as e:
							sentry_sdk.capture_exception(e)
							self.showError(
								'Neuer Vertretungsplan', 
								'Vertretungsplan konnte nicht verarbeitet ' + \
								'werden, weil die Datei fehlerhaft ist.'
							)
							print('Error: %s' % (str(e),))
							traceback.print_exc()
							self.dlg.addError(str(e))
							#FIXME: self.showDlg.emit()
							raise
					print('Ending transaction {}'.format(transName))
					transaction.finish()
					# for untis, we parse only the first one!
					if handler.onlyFirstFile():
						break
				else:
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

	def sendPlan(self, transaction, table, absFile, planType='all'):
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
			values = urllib.parse.urlencode(values)

			if self.getOption('debugOnline'):
				values['XDEBUG_SESSION_START'] = '1'

			proxies = None
			if self.isProxyEnabled():
				print('Proxy is activated')
				httpproxy = "http://"+self.config.get("proxy", "phost")+":"+self.config.get("proxy", "pport")
				proxies = {
					"http" : httpproxy,
					"https": httpproxy
				}
				transaction.set_data('http.proxy_uri', httpproxy)
				transaction.set_tag('http.proxy', True)
			else:
				print('Proxy is deactivated')
				transaction.set_tag('http.proxy', False)
			
			headers = {}
			httpauth = None
			if self.config.has_option("siteauth", "enable") and self.config.get("siteauth", "enable") == 'True':
				httpauth = HTTPBasicAuth(
					self.config.get('siteauth', 'username'),
					self.config.get('siteauth', 'password')
				)
				transaction.set_tag('http.basic_auth', True)
			else:
				transaction.set_tag('http.basic_auth', False)

			# add post info
			headers['Content-Type'] = 'application/x-www-form-urlencoded;charset=utf-8'

			errorMessage = None
			errObj = None
			try:
				req = requests.post(self.getSendURL(), data=values, proxies=proxies, headers=headers, auth=httpauth)
			except requests.exceptions.ConnectionError as err:
				self.createCoreDump(err)
				errorMessage = (
					'Warnung',
					'Der Vertretungsplan konnte eventuell nicht korrekt hochgeladen werden. '
					'Bitte kontaktieren Sie das Website-Team der FLS! '
					'Beim Hochladen konnte keine Verbindung zum Server aufgebaut werden.'
				)
				errObj = err
				print('HTTP-Fehler aufgetreten: {:s}'.format(str(err)))
				sentry_sdk.capture_exception(err)
			except urllib.error.URLError as err:
				self.createCoreDump(err)
				errorMessasge = (
					'Warnung',
					'Der Vertretungsplan konnte eventuell nicht korrekt hochgeladen werden. \
					Bitte kontaktieren Sie das Website-Team der FLS!'
				)
				errObj = err
				print('URL-Fehler aufgetreten: {:s}'.format(err.reason))
				sentry_sdk.capture_exception(err)
			except Exception as err:
				self.createCoreDump(err)
				errorMessage = (
					'Warnung',
					'Der Vertretungsplan konnte eventuell nicht korrekt hochgeladen werden. \
					Bitte kontaktieren Sie das Website-Team der FLS!'
				)
				errObj = err
				print("Unbekannter Fehler aufgetreten: ", err)
				sentry_sdk.capture_exception(err)
			else:
				transaction.set_tag('http.status_code', req.status_code)
				transaction.set_data('http.text', req.text)
				if req.status_code != 204:
					errorMessage = (
						'Warnung',
						'Der Vertretungsplan konnte eventuell nicht korrekt hochgeladen werden. '
						'Es wurde ein abweichender Statuscode erhalten: {:d}'.format(req.status_code)
					)
					errObj = req.text
				else:
					print(req.text)
					print('Erfolgreich hochgeladen.')
			
			# any error to show in detail to user?
			if errorMessage:
				transaction.set_data('vplan.send_error', errorMessage)
				if errObj:
					self.dlg.addData(str(errObj))
				self.showError(*errorMessage)
				self.dlg.addError(errorMessage[1])
			else:
				self.showInfo('Vertretungsplan hochgeladen', 'Die Datei wurde erfolgreich hochgeladen.')

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
		folderPath = os.path.dirname(path)
		if self.config.get('options', 'delFolder') == 'True' and os.path.exists(folderPath):
			for filename in glob.iglob(folderPath + '/*'):
				try:
					os.remove(filename)
				except:
					pass

		self.lastFile = newFile

	def parsePlanByHandler(self, transaction, hdl, fileName):
		# send a notification
		self.showInfo('Neuer Vertretungsplan', 'Es wurde eine neue Datei gefunden und wird jetzt verarbeitet.')
		absPath = os.path.join(self.config.get('default', 'path'), fileName)
		djp = hdl(self.config, self.dlg, absPath)
		djp.planFileLoaded.connect(self.planFileLoaded)
		djp.planParserPrepared.connect(self.planParserPrepared)
		with transaction.start_child(op='parse::loadFile', description=fileName) as transChild:
			djp.loadFile(transChild)
		
		with transaction.start_child(op='parse::preParse', description=fileName):
			djp.preParse(transChild)

		with transaction.start_child(op='parse::parse', description=fileName):
			djp.parse(transChild)
		
		with transaction.start_child(op='parse::postParse', description=fileName):
			djp.postParse(transChild)
		
		data = djp.getResult()
		data['system'] = {
			'version': __version__,
			'handler': hdl.__name__,
			'fname': absPath
		}
		self.showInfo('Neuer Vertretungsplan', 'Vertretungsplan wurde verarbeitet und wird nun hochgeladen.')

		with transaction.start_child(op='parse::sendPlan', description=fileName):
			self.sendPlan(transChild, data, absPath)

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

	def initSentry(self):
		# check if sentry is enabled.
		if not self.config.getboolean('sentry', 'enable', fallback=False) \
			or not self.config.get('sentry', 'sendsn', fallback=None):
			return

		try:
			import sentry_sdk
		except:
			pass
		else:
			# proxy settings?
			if self.isProxyEnabled():
				httpproxy = "http://"+self.config.get("proxy", "phost")+":"+self.config.get("proxy", "pport")
			else:
				httpproxy = None

			def logSentrySend(event, hint):
				print('Now sending sentry data!!!')

			sentry_sdk.init(
				self.config.get('sentry', 'sendsn'),
				max_breadcrumbs=self.config.getint('sentry', 'maxBreadcrumbs', fallback=50),
				debug=self.config.getboolean('sentry', 'debug', fallback=False),
				send_default_pii=self.config.getboolean('sentry', 'pii', fallback=False),
				environment=self.config.get('sentry', 'environment', fallback=None),
				sample_rate=self.config.getfloat('sentry', 'sampleRate', fallback=1.0),
				traces_sample_rate=self.config.getfloat('sentry', 'tracesSampleRate', fallback=1.0),
				http_proxy=httpproxy,
				https_proxy=httpproxy,
				before_send=logSentrySend,
				release=__version__
			)
			self._sentryEnabled = True

	def __init__(self):
		super().__init__()

		self.lastFile = ''
		self.run = True
		self.config = None
		self.tray = None
		self.search = None
		self.before = None
		self.locked = False
		self._sentryEnabled = False

		self.loadConfig()
		self.initSentry()
		self.initTray()

		debugLog = self.config.getboolean('options', 'debugLogs', fallback=False)

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
