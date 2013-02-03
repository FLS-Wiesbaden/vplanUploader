#!/usr/bin/env python3
# -*- coding: utf8 -*-
#
# @author Lukas Schreiner
#

import urllib.request, urllib.parse, urllib.error, traceback, sys
import time, os, os.path, json, codecs, base64, configparser, shutil
from TableParser import TableParser
from layout_scanner import *
from searchplaner import *
from threading import Thread
from Printer import Printer
from pprint import pprint
from pydump import pydump
from datetime import datetime

app = None
if os.name in 'nt':
	import win32gui
elif os.name == 'posix':
	#from PyQt4 import QtGui
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

class Vertretungsplaner:

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
		if self.tray is not None:
			self.tray.showInfo(title, msg)
		return 0

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
				if f.lower().endswith('.html') or f.lower().endswith('.htm'):
					Thread(target=self.handlingPlaner, args=(f,)).start()
				elif f.lower().endswith('.pdf'):
					Thread(target=self.handlingCanceledPlan, args=(f, )).start()
				else:
					print('"%s" will be ignored.' % f)

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

	def loadFile(self,absFile):
		f = open(absFile, 'rb')
		dtaContents = f.read()
		f.close()

		try:
			dtaContents = dtaContents.decode('iso-8859-1')
		except:
			try:
				dtaContents = dtaContents.decode('utf8')
			except:
				print('Nothing possible to decode!')

		return dtaContents


	def parse_table(self, dtaContents):
		p = TableParser(dtaContents)
		table = p.getTable()
		return table[3:]

	def convert(self, table):
		for i,v in enumerate(table):
			for k,x in enumerate(v):
				if self.filesAreUTF8() and type(x).__name__ != 'str':
					table[i][k] = x.decode("utf8")
				elif type(x).__name__ != 'str':
					print(type(x).__name__)
					table[i][k] = x.decode("iso-8859-1")

				#table[i][k] = self.replaceUmlaute(x)
				#table[i][k] = x.encode("utf8")

		return table

	def replaceUmlaute(self, data):
		#ue
		data = data.replace(chr(252), '&uuml;')
		data = data.replace(chr(220), '&Uuml;')

		#ae
		data = data.replace(chr(228), '&auml;')
		data = data.replace(chr(196), '&Auml;')

		#oe
		data = data.replace(chr(246), '&ouml;')
		data = data.replace(chr(214), '&Ouml;')

		#ss
		data = data.replace(chr(223), '&szlig;')

		return data

	def send_table(self, table, absFile, planType, convert = True):
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

		try:
			response = opener.open(request)
			code = response.read()
			self.showToolTip('Vertretungsplan hochgeladen','Die Datei wurde erfolgreich hochgeladen.','info')

			print('Erfolgreich hochgeladen.')
		except urllib.error.URLError as err:
			self.createCoreDump()
			self.showToolTip('Uploadfehler!','Die Datei konnte eventuell nicht hochgeladen werden. Bitte kontaktieren Sie das Website-Team der FLS!','error')
			print("URL-Fehler aufgetreten: %s" % ( err.reason, ))
		except urllib.error.HTTPError as err:
			self.createCoreDump()
			self.showToolTip('Uploadfehler!','Die Datei konnte eventuell nicht hochgeladen werden. Bitte kontaktieren Sie das Website-Team der FLS!','error')
			print("HTTP-Fehler aufgetreten: %i - %s" % ( err.code, err.reason ))
		except Exception as err:
			self.createCoreDump()
			self.showToolTip('Uploadfehler!','Die Datei konnte eventuell nicht hochgeladen werden. Bitte kontaktieren Sie das Website-Team der FLS!','error')
			print("Unbekannter Fehler aufgetreten: ", err)

		# now move the file and save an backup. Also delete the older one.
		self.moveAndDeleteVPlanFile(absFile)

	def createCoreDump(self):
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

		pydump.save_dump(filename)
		print('Coredump created in %s' % (filename,))

	def moveAndDeleteVPlanFile(self, absFile):
		# file => Actual file (move to lastFile)
		# self.lastFile => last File (delete)
		path = absFile
		if os.path.exists(self.lastFile) and self.lastFile != '':
			# delete
			os.remove(self.lastFile)
			print('Datei %s entfernt' % (self.lastFile))
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

	def handlingPlaner(self,fileName):
		path = self.getWatchPath()
		sep = os.sep
		absPath = path+sep+fileName
		tmp = False

		print("\nThis is what you want: ", absPath)
		try:
			tmp = self.loadFile(absPath)
			tmp = self.parse_table(tmp)
		except Exception as detail:
			tmp = False
			print('Err ', detail)
			print('-'*60)
			traceback.print_exc(file=sys.stdout)
			print('-'*60)

		if tmp != False:
			self.showToolTip('Neuer Vertretungsplan','Es wurde eine neue Datei gefunden! Sie wird jetzt hochgeladen.','info')
			# number columns
			cols = 0
			try:
				cols = len(tmp[0])
			except KeyError as e:
				cols = 0
			if cols < 10:
				planType = 'canceled'
				tmp = self.convert_to_canceled(tmp)
			else:
				planType = 'fillin'
			self.send_table(tmp, absPath, planType)
		else:
			print('Datei gefunden, die keine Tabelle enthaelt!')

	def handlingCanceledPlan(self,fileName):
		path = self.getWatchPath()
		sep = os.sep
		absPath = path+sep+fileName
		tmp = False

		print("\nThis is what you want: ", absPath)
		try:
			tmp = self.parse_canceledPlan(absPath)
			pprint(tmp)
			for k,v in tmp['plan'].items():
				print('Anzahl abbestellter Klassen fuer Tag %s: %i' % (k, len(tmp['plan'][k])))
		except Exception as detail:
			tmp = False
			print('Err ', detail)

		if tmp != False:
			print('Infos gefunden!')
			self.showToolTip('Neuer Vertretungsplan','Es wurde ein neues PDF-Dokument gefunden! Es wird jetzt hochgeladen.','info')
			self.send_table(tmp, absPath, 'canceled', convert=False)
		else:
			print('Datei gefunden, die keine Infos enthaelt!')

	def convert_to_canceled(self, tmp):
		resultObj = {'stand': int(time.time()), 'plan': {}}

		for row in tmp:
			day, month, year = row[0].strip().split('.')
			mysqldate = '%s-%s-%s' % (year, month, day)
			if mysqldate not in resultObj['plan']:
				resultObj['plan'][mysqldate] = []
			resultObj['plan'][mysqldate].append({'number': row[6].strip(), 'info': '%s-%s' % (row[2], row[5]), 'note': row[7]})

		return resultObj

	def parse_canceledPlan(self, absPath):
		resultObj = {'stand': int(time.time()), 'plan': {}}
		pages = get_pages(absPath)
		if pages is None:
			pages = []

		for f in pages:
			retList = self.parse_page(f)
			for k,v in retList.items():
				resultObj['plan'][k] = v

		return resultObj

	def parse_page(self, page):
		planDays = []
		cancelled = []
		result = {}
		days = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']

		lines = page.split('\n')

		# check for existent lines
		if len(lines) <= 0:
			return result

		# check whether the first entry is an date
		date = weekday = day = month = year = None
		try:
			weekday, date = lines[0].strip().split(' ')
			day, month, year = date.split('.')
		except Exception:
			# there was an error: this means bye, bye!
			return result

		# now check weekday
		if weekday is None or weekday not in days:
			return result

		# now gets the dates
		pos = 0
		while not lines[pos].strip().startswith('Fehlende Klassen') and pos < len(lines):
			try:
				weekday, date = lines[pos].strip().split(' ')
				day, month, year = date.split('.')
				dateStr = '%s-%s-%s' % (year, month, day)
				if weekday in days:
					planDays.append(dateStr)
			except:
				# nothing
				date = None
			pos += 1

		# now we have all days saved. But if we have nothing found: break
		if len(planDays) <= 0 or pos >= len(lines):
			return result

		# so we have things found up. Now lets try to find the assigned cancelled classes
		# next line have to be start with "Fehlende Klassen"
		if not lines[pos].strip().startswith('Fehlende Klassen'):
			return result

		classes = []
		while (len(lines[pos].strip()) > 0 or lines[pos + 1].strip().startswith('Fehlende Klassen')) \
				and pos < len(lines):
				if lines[pos].strip().startswith('Fehlende Klassen') and len(classes) > 0:
					cancelled.append(self.interpret_classes(classes))
					classes = []

				classes.append(lines[pos].strip())
				pos += 1

		if len(classes) > 0:
			cancelled.append(self.interpret_classes(classes))
			classes = []

		# now connect things!
		if len(planDays) != len(cancelled):
			print('We have found %i days and %i classes information. We have no association!' % (len(planDays), len(cancelled)))

		for k,v in enumerate(planDays):
			result[v] = cancelled[k]

		return result

	def interpret_classes(self, classes):
		# now we saved all things. It will be difficult now, because we have to split all things.
		# 1. remove text
		classes[0] = classes[0].replace('Fehlende Klassen:', '')
		classes = ' '.join(classes).split(';')
		for k,v in enumerate(classes):
			v = v.strip().split(' ')
			info = {'number': '', 'info': ''}
			info['number'] = v[0]
			del(v[0])
			del(v[0])
			del(v[0])

			if len(v) > 1:
				v[1] = v[1].replace(')','')
			elif len(v) > 0:
				v[0] = v[0].replace(')','')

			info['info'] = ''.join(v)

			classes[k] = info

		return classes


	def loadConfig(self):
		self.config = configparser.ConfigParser()
		self.config.read("config.ini")

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

	def __del__(self):
		if os.path.exists(self.lastFile):
			os.remove(self.lastFile)
			self.lastFile = ''

app = Vertretungsplaner()

if os.name in 'nt':
	win32gui.PumpMessages()
elif os.name == 'posix':
	#sys.exit(pyapp.exec_())
	pass
