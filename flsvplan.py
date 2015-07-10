#!/usr/bin/env python3
# -*- coding: utf8 -*-
#
# @author Lukas Schreiner
#

import urllib.request, urllib.parse, urllib.error, traceback, sys, re
import time, os, os.path, json, codecs, base64, configparser, shutil, csv
from xml.dom import minidom 
from TableParser import TableParser
from layout_scanner import *
from searchplaner import *
from threading import Thread
from Printer import Printer
from datetime import datetime
import pickle
import traceback
import inspect

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
					# switch version
					if int(self.config.get('vplan', 'version')) == 5:
						if f.lower().endswith('.html') or f.lower().endswith('.htm'):
							execFound = True
							Thread(target=self.handlingPlaner, args=(f,)).start()
						elif f.lower().endswith('.pdf'):
							execFound = True
							Thread(target=self.handlingCanceledPlan, args=(f, )).start()
					elif int(self.config.get('vplan', 'version')) == 6:
						if f.lower().endswith('.csv') or f.lower().endswith('.txt'):
							execFound = True
							Thread(target=self.handlingDavinciSixStandIn, args=(f,)).start()
						elif f.lower().endswith('.xml'):
							execFound = True
							Thread(target=self.handlingDavinciXml, args=(f,)).start()
						elif f.lower().endswith('.json'):
							execFound = True
							Thread(target=self.handlingDavinciJson, args=(f,)).start()
				if f.lower().endswith('.json') and not execFound:
					execFound = True
					Thread(target=self.handlingJson, args=(f,)).start()
				elif not execFound:
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
		try:
			table = p.getTable()
			return table[3:]
		except:
			return []

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
		dump['url'] = err.geturl()
		dump['code'] = err.getcode()
		dump['info'] = err.info()
		dump['hdrs'] = err.hdrs
		dump['msg'] = err.msg
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
			except IndexError as e:
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

	def getFieldContent(self, row, field):
		if field == 'posend' and self.config.getint('fields', field) < 0:
			field = 'pos'

		if self.config.getint('fields', field) < 0:
			return ''
		else:
			return row[self.config.getint('fields', field)].strip()

	def handlingDavinciSixStandIn(self, fileName):
		# some patterns (better don't ask which possibilities we have).
		pattTeacher = re.compile(r'^(((\+([-a-zA-ZÄÖÜäöü,\.]+)) )?\(([-a-zA-ZÄÖÜäöü,\.]+)\))|([-a-zA-ZÄÖÜäöü,\.]+)$')
		pattSubject = re.compile(r'^(((\+([a-zA-ZÄÖÜäöü]+)) )?\(([a-zA-ZÄÖÜäöü]+)\))|([a-zA-ZÄÖÜäöü]+)$')
		pattRoom = re.compile(r'^(|[a-zA-Z0-9 ]+|((\+([a-zA-Z0-9 ]+))(, [a-zA-Z0-9 ]+)* )?\(([a-zA-Z0-9 ]+)(, [a-zA-Z0-9 ]+)?\))$')
		pattMoved = re.compile(r'^[A-Za-z]+\ (\d{1,2})\.(\d{1,2})\.\ ([a-zA-Z]{2})\ (\d{1,2})\ [a-zA-Z]+$')

		# send a notification
		self.showToolTip('Neuer Vertretungsplan','Es wurde eine neue Datei gefunden! Sie wird jetzt verarbeitet.','info')

		# ok... and now try to read the file.
		path = self.getWatchPath()
		sep = os.sep
		absPath = path+sep+fileName
		delim = self.config.get('vplan', 'colsep')
		if delim == '\\t':
			delim = '\t'
		try:
			f = open(absPath, 'r', encoding='utf-8' if self.filesAreUTF8() else 'iso-8859-1')
			reader = csv.reader(f, delimiter=delim)

			data = {'stand': int(time.time()), 'plan': []}
			for row in reader:
				# empty line?
				if ''.join(row).strip() == '':
					continue

				# is it really a standin plan?
				if len(row) <= 6:
					# try to read cancelled... but only when enabled!
					if self.config.getboolean('vplan', 'cancelled'):
						data['plan'] = self.handlingDavinciSixCancelled(fileName)
					break
				
				# get first the type.
				chgtype = self.getFieldContent(row, 'type')
				chgkind = self.getFieldContent(row, 'kind')
				# ok.. it is some kind of yard duty change.
				if chgtype == self.config.get('changetype', 'yarddutyChange'):
					yd = self.handlingYardDuty(row)
					if yd is not None:
						data['plan'].append(yd)
					continue

				# now lets define the structure:
				r = {
					'type': 1,
					'date': '',
					'hour': None,
					'starttime': None,
					'endtime': None,
					'teacher': None,
					'subject': None,
					'room': None,
					'course': None,
					'chgteacher': None,
					'chgsubject': None,
					'chgroom': None,
					'notes': '',
					'info': ''
				}

				# first the class.
				chgclass = self.getFieldContent(row, 'class')
				# skip empty classes.
				if len(chgclass) <= 0:
					continue
				else:
					r['course'] = chgclass

				# date, hour, info, note
				r['date'] = self.getFieldContent(row, 'date')
				r['hour'] = self.getFieldContent(row, 'pos')
				r['info'] = self.getFieldContent(row, 'info')
				r['notes'] = self.getFieldContent(row, 'note')

				# room.
				rawRoom = self.getFieldContent(row, 'room')
				try:
					roomMatch = pattRoom.match(rawRoom)
				except Exception as e:
					roomMatch = None
					print(e, row)
				oldRoom = None
				newRoom = None
				if roomMatch is not None:
					newRoom, oldRoom = self.parseRoom(rawRoom, roomMatch)
				r['room'] = oldRoom if oldRoom is not None else ''
				r['chgroom'] = newRoom if newRoom is not None else ''

				# subject (i didn't saw the "+" anywhere.. but just to be sure)
				rawSubject = self.getFieldContent(row, 'subject')
				subjectMatch = pattSubject.match(rawSubject)
				oldSubj = None
				newSubj = None
				if subjectMatch is not None:
					if subjectMatch.group(6) is None:
						newSubj = subjectMatch.group(4)
						oldSubj = subjectMatch.group(5)
					else:
						oldSubj = subjectMatch.group(6)
				r['subject'] = oldSubj if oldSubj is not None else ''
				r['chgsubject'] = newSubj if newSubj is not None else ''

				# teacher
				rawTeacher = self.getFieldContent(row, 'teacher')
				teacherMatch = pattTeacher.match(rawTeacher)
				oldTeacher = None
				newTeacher = None
				if teacherMatch is not None:
					if teacherMatch.group(6) is None:
						newTeacher = teacherMatch.group(4)
						oldTeacher = teacherMatch.group(5)
					else:
						oldTeacher = teacherMatch.group(6)
				r['teacher'] = oldTeacher if oldTeacher is not None else ''
				r['chgteacher'] = newTeacher if newTeacher is not None else ''

				# get the times
				entryTime = self.getFieldContent(row, 'time')
				starttime = None
				endtime = None
				if '-' in entryTime:
					starttime, endtime = entryTime.split('-')
					if len(starttime) <= 5:
						starttime = starttime + ':00'
					if len(endtime) <= 5:
						endtime = endtime + ':00'
				r['starttime'] = starttime
				r['endtime'] = endtime

				# if class is missing => set the note "Frei"
				if len(r['info']) <= 0 and chgkind == self.config.get('changekind', 'classFree'):
					r['notes'] = self.config.get('vplan', 'txtReplaceFree')
				# maybe it was moved?
				elif self.config.get('changekind', 'moved').lower() in chgkind:
					moveMatch = pattMoved.match(row[1].strip())
					if moveMatch is not None:
						day, month, weekday, hour = moveMatch.groups()
						day = int(day)
						month = int(month)
						hour = int(hour)
						r['info'] = self.config.get('vplan', 'txtMovedInfo')
						r['notes'] = self.config.get('vplan', 'txtMovedNote').format(weekday, hour, day, month)

				chgclass = chgclass.split(',')
				for cl in chgclass:
					r['class'] = cl.strip()
					start = int(self.getFieldContent(row, 'pos'))
					end = int(self.getFieldContent(row, 'posend'))
					while start <= end:
						r['hour'] = start
						data['plan'].append(r)
						start += 1

			f.close()
			self.showToolTip('Neuer Vertretungsplan','Vertretungsplan wurde verarbeitet. Er wird nun hochgeladen.','info')
			self.send_table(data, absPath)
		except Exception as e:
			self.showToolTip('Neuer Vertretungsplan','Vertretungsplan konnte nicht verarbeitet werden. Datei ist fehlerhaft.','error')
			print('Error: %s' % (str(e),))

	def handlingDavinciSixCancelled(self, fileName):
		path = self.getWatchPath()
		sep = os.sep
		absPath = path+sep+fileName
		f = open(absPath, 'r', encoding='utf-8' if self.filesAreUTF8() else 'iso-8859-1')
		reader = csv.reader(f, delimiter=';')

		data = []
		for row in reader:
			try:
				date, hours, teacher, subject, className, info, room, note = row
			except ValueError:
				# might be a empty line :)
				continue

			try:
				day, month, year = date.split('.')
			except ValueError:
				# uhh it might be the first line: skip!
				continue
			entryDate = '%s.%s.%s' % (day, month, year)

			try:
				hours = hours.strip().split('-');
				hours[0] = int(hours[0].replace('.', '').strip())
				if len(hours) > 1:
					hours[1] = int(hours[1].replace('.', '').strip())
				else:
					hours.append(hours[0])
			except Exception as e:
				print('Got error: %s' % (e,))
				continue

			for hour in range(hours[0], hours[1] + 1):
				r = {
					'type': 2,
					'date': entryDate,
					'hour': hour,
					'starttime': None,
					'endtime': None,
					'teacher': teacher,
					'subject': subject,
					'room': room,
					'course': None,
					'chgteacher': None,
					'chgsubject': None,
					'chgroom': None,
					'notes': note,
					'info': info
				}
				r['course'] = className.strip()

				data.append(r)

		return data

	def handlingDavinciXml(self, fileName):
		# some patterns (better don't ask which possibilities we have).
		pattTeacher = re.compile(r'^(((\+([-a-zA-ZÄÖÜäöü,\.]+)) )?\(([-a-zA-ZÄÖÜäöü,\.]+)\))|([-a-zA-ZÄÖÜäöü,\.]+)$')
		pattSubject = re.compile(r'^(((\+([a-zA-ZÄÖÜäöü]+)) )?\(([a-zA-ZÄÖÜäöü]+)\))|([a-zA-ZÄÖÜäöü]+)$')
		pattRoom = re.compile(r'^(|[a-zA-Z0-9 ]+|((\+([a-zA-Z0-9 ]+))(, [a-zA-Z0-9 ]+)* )?\(([a-zA-Z0-9 ]+)(, [a-zA-Z0-9 ]+)?\))$')
		pattMoved = re.compile(r'^[A-Za-z]+\ (\d{1,2})\.(\d{1,2})\.\ ([a-zA-Z]{2})\ (\d{1,2})\ [a-zA-Z]+$')
		pattClass = re.compile(r'^(\((([-a-zA-Z0-9 ])+(, )?)*\)(, )?)?((([-a-zA-Z0-9 ]+)(, )?)*)?$')
		pattMovedFrom = re.compile(self.config.get('changekind', 'movedFrom'))
		pattMovedTo = re.compile(self.config.get('changekind', 'movedTo'))

		# send a notification
		self.showToolTip('Neuer Vertretungsplan','Es wurde eine neue Datei gefunden! Sie wird jetzt verarbeitet.','info')

		# ok... and now try to read the file.
		path = self.getWatchPath()
		sep = os.sep
		absPath = path+sep+fileName

		absentClasses = {}
		
		try:
			f = open(absPath, 'r', encoding='utf-8' if self.filesAreUTF8() else 'iso-8859-1')
			reader = minidom.parse(f)
			data = {'stand': int(time.time()), 'plan': []}

			# we are only interested in "Lessons"
			lessons = reader.getElementsByTagName('daysubstclass')
			for les in lessons:
				lesList = les.getElementsByTagName('Day')
				for day in lesList:
					itemList = day.getElementsByTagName('Item')
					for l in itemList:
						startPos = int(self.getXmlRaw(l.getElementsByTagName('Pos')[0]))
						endPos = int(self.getXmlRaw(l.getElementsByTagName('Until')[0]))
						classes = []
						absClasses = []
						chgType = 0
						planType = 1

						rawDate = self.getXmlRaw(l.getElementsByTagName('Date')[0])
						entryDate = '%s.%s.%s' % (rawDate[6:], rawDate[4:6], rawDate[:4])
						absentClasses[entryDate] = []
						rawStartTime = l.getElementsByTagName('Start')
						rawEndTime = l.getElementsByTagName('Finish')
						startTime = None
						finishTime = None
						if len(rawStartTime) > 0:
							rawStartTime = self.getXmlRaw(rawStartTime[0])
							startTime = '%s:%s:00' % (rawStartTime[:2], rawStartTime[2:4])

						if len(rawEndTime) > 0:
							rawEndTime = self.getXmlRaw(rawEndTime[0])
							finishTime = '%s:%s:00' % (rawEndTime[:2], rawEndTime[2:4])

						# Subject
						subject = None
						rawSubject = l.getElementsByTagName('Title')
						if len(rawSubject) > 0:
							chgsubject = self.getXmlRaw(rawSubject[0])
							# maybe its given in subject.
							subjectMatch = pattSubject.match(chgsubject)
							oldSubj = None
							newSubj = None
							if subjectMatch is not None:
								if subjectMatch.group(6) is None:
									newSubj = subjectMatch.group(4)
									oldSubj = subjectMatch.group(5)
								else:
									oldSubj = subjectMatch.group(6)
								subject = oldSubj
								chgsubject = newSubj
							else:
								subject = chgsubject
								chgsubject = None
						else:
							subjct = None
							chgsubject = None

						# Change Room
						rawRoom = l.getElementsByTagName('Room')
						room = None
						if len(rawRoom) > 0:
							chgroom = self.getXmlRaw(rawRoom[0])
							rawRoom = chgroom
							try:
								roomMatch = pattRoom.match(rawRoom)
							except Exception as e:
								roomMatch = None
								print(e, rawRoom)
							oldRoom = None
							newRoom = None
							if roomMatch is not None:
								newRoom, oldRoom = self.parseRoom(rawRoom, roomMatch)
								if oldRoom is None and newRoom is not None:
									room = newRoom
								elif oldRoom is not None and newRoom is not None:
									room = oldRoom
									chgroom = newRoom
								else:
									room = rawRoom
							else:
								room = rawRoom
								chgroom = None
						else:
							room = None
							chgroom = None

						if room == chgroom:
							chgroom = None
						
						# Change Teacher
						rawTeachers = l.getElementsByTagName('Teacher')
						if len(rawTeachers) > 0:
							chgteacher = self.getXmlRaw(rawTeachers[0])
							teacherMatch = pattTeacher.match(chgteacher)
							oldTeacher = None
							newTeacher = None
							if teacherMatch is not None:
								if teacherMatch.group(6) is None:
									newTeacher = teacherMatch.group(4)
									oldTeacher = teacherMatch.group(5)
								else:
									oldTeacher = teacherMatch.group(6)
								teacher = oldTeacher
								chgteacher = newTeacher
							else:
								teacher = chgteacher
								chgteacher = None
						else:
							teacher = None
							chgteacher = None

						# additional info
						note = ''
						info = ''

						rawInfo = l.getElementsByTagName('Caption')
						if len(rawInfo) > 0:
							info = self.getXmlRaw(rawInfo[0])

						# remove some kind of infos.
						if len(info) > 0:
							if info in self.config.get('vplan', 'rmvInfos').split(';'):
								info = ''

						# some movement info?
						# here, we support advanced regexp.
						if len(info) > 0:
							tstMove = pattMovedFrom.match(info)
							if tstMove is not None:
								day, month, non = tstMove.group(1).split('.')
								weekday = tstMove.group(2)
								mvstr = tstMove.group(3)
								mvend = tstMove.group(5)
								if mvend is not None:
									hour = '%s.-%s.' % (mvstr, mvend)
								else:
									hour = '%s.' % (mvstr,)
								info = ''
								note = self.config.get('vplan', 'txtMovedNote').format(weekday, hour, int(day), int(month))
								chgType = 32
							else:
								tstMove = pattMovedTo.match(info)
								if tstMove is not None:
									day, month, non = tstMove.group(1).split('.')
									weekday = tstMove.group(2)
									mvstr = tstMove.group(3)
									mvend = tstMove.group(5)
									if mvend is not None:
										hour = '%s.-%s.' % (mvstr, mvend)
									else:
										hour = '%s.' % (mvstr,)
									info = self.config.get('vplan', 'txtMoved').format(weekday, hour, int(day), int(month))
									chgType = 16
								elif info == self.config.get('changekind', 'classFree'):
									chgType = 64

						# get the list of affected classes
						cl = self.getXmlRaw(l.getElementsByTagName('Class')[0]).strip()
						clM = pattClass.match(cl)
						if clM is None:
							classes.append(cl)
						else:
							# first is always absent!
							absent = clM.group(1)
							if absent is not None:
								absent = absent.strip()[1:-1]
								if absent[-1:] == ')':
									absent = absent[:-1]
								for i in absent.split(', '):
									absClasses.append(i)
									classes.append(i)
								planType = 2
								chgType = 1

							if chgType != 1:
								try:
									strGroup = 6
									endGroup = len(clM.groups()) - 3
									for idx in range(strGroup, endGroup + 1):
										normal = clM.group(idx)
										if normal is not None:
											if ', ' in normal:
												for cl in normal.split(', '):
													classes.append(cl)
											else:
												classes.append(normal)
								except Exception as e:
									print('Could not retrieve class names because of %s' % (str(e),))

						# now generate the records
						for className in classes:
							if className in absClasses:
								newNote = self.config.get('vplan', 'txtReplaceFree')
							else:
								newNote = note

							for hour in range(startPos, endPos + 1):
								r = {
									'type': planType,
									'date': entryDate,
									'hour': hour,
									'starttime': startTime,
									'endtime': finishTime,
									'teacher': teacher,
									'subject': subject,
									'room': room,
									'chgType': chgType,
									'course': None,
									'chgteacher': chgteacher,
									'chgsubject': chgsubject,
									'chgroom': chgroom,
									'notes': newNote,
									'info': info
								}
								r['course'] = className.strip()
								# in case of cancelled class: remove all data!
								if planType == 2:
									r['teacher'] = None
									r['subject'] = None
									r['room'] = None
									r['chgteacher'] = None
									r['chgsubject'] = None
									r['chgroom'] = None
									r['notes'] = ''
									r['hour'] = 0

								exist = False
								# does it already exist there?
								for entry in data['plan']:
									if entry['date'] == r['date'] \
									 and entry['hour'] == r['hour'] \
									 and entry['course'] == r['course'] \
									 and entry['teacher'] == r['teacher'] \
									 and entry['subject'] == r['subject'] \
									 and entry['room'] == r['room']:
										exist = True
										break

								if not exist:
									data['plan'].append(r)

			f.close()
			self.showToolTip('Neuer Vertretungsplan','Vertretungsplan wurde verarbeitet. Er wird nun hochgeladen.','info')
			self.send_table(data, absPath)
		except Exception as e:
			self.showToolTip('Neuer Vertretungsplan','Vertretungsplan konnte nicht verarbeitet werden. Datei ist fehlerhaft.','error')
			print('Error: %s' % (str(e),))

	def handlingDavinciJson(self, fileName):
		# some patterns (better don't ask which possibilities we have).
		pattMovedFrom = re.compile(self.config.get('changekind', 'movedFrom'))
		pattMovedTo = re.compile(self.config.get('changekind', 'movedTo'))

		# send a notification
		self.showToolTip('Neuer Vertretungsplan','Es wurde eine neue Datei gefunden! Sie wird jetzt verarbeitet.','info')

		# ok... and now try to read the file.
		path = self.getWatchPath()
		sep = os.sep
		absPath = path+sep+fileName

		absentClasses = {}
		
		try:
			planContent = None
			with open(absPath, 'rb') as f:
				planContent = f.read()

			if planContent is None:
				raise Exception('Could not read the plan!')

			if self.filesAreUTF8():
				try:
					planContent = json.loads(planContent.decode('utf-8'))
				except:
					planContent = json.loads(planContent.decode('utf-8-sig'))
			else:
				planContent = json.loads(planContent.decode('iso-8859-1'))

			data = {'stand': int(time.time()), 'plan': [], 'class': {}}
			
			# first load the time frames to obtain the "hours"
			timeframes = {}
			for tf in planContent['result']['timeframes']:
				if tf['code'] == 'Standard':
					for t in tf['timeslots']:
						timeframes[t['startTime']] = int(t['label'])

			# teams
			teams = {}
			for tf in planContent['result']['teams']:
				teams[tf['id']] = tf['description']

			# build the class dict
			for tf in planContent['result']['classes']:
				data['class'][tf['code']] = ''
				for tr in tf['teamRefs']:
					if len(tr) > 0:
						if tr in teams.keys():
							data['class'][tf['code']] = teams[tr]

			# we are only interested in the displaySchedule of result
			for les in planContent['result']['displaySchedule']['lessonTimes']:
				# ignore this entry, if there is no changes block.
				if 'changes' not in les.keys():
					continue

				# now take the changes block.
				planType = 1
				entryDates = []
				hour = None
				startTime = None
				endTime = None
				teacher = None
				subject = None
				room = None
				chgType = None
				courses = []
				chgTeacher = None
				chgSubject = None
				chgRoom = None
				notes = ''
				info = ''

				# Dates, Hours, Times
				for dt in les['dates']:
					entryDates.append('%s.%s.%s' % (dt[6:], dt[4:6], dt[:4]))

				# The times are now mandatory because of the timetable.
				startTime = '%s:%s:00' % (les['startTime'][:2], les['startTime'][2:4])
				endTime = '%s:%s:00' % (les['endTime'][:2], les['endTime'][2:4])
				hour = timeframes[les['startTime']]
				try:
					subject = les['subjectCode']
				except KeyError as e:
					# is it allowed, if the reasonType == classAbsence!
					if 'reasonType' not in les['changes'].keys() or les['changes']['reasonType'] != 'classAbsence':
						continue
						#raise

				# courses
				for cl in les['classCodes']:
					courses.append(cl)

				# the teacher (strange that it is a list)
				try:
					for t in les['teacherCodes']:
						teacher = t
						break
				except KeyError as e:
					# is it allowed, if the reasonType == classAbsence!
					if 'reasonType' not in les['changes'].keys() or les['changes']['reasonType'] != 'classAbsence':
						raise

				# Room (we also consider here only the first)
				try:
					for r in les['roomCodes']:
						room = r
						break
				except KeyError as e:
					# is it allowed, if the reasonType == classAbsence!
					if 'reasonType' not in les['changes'].keys() or les['changes']['reasonType'] != 'classAbsence':
						raise

				# some information?
				if 'caption' in les['changes'].keys():
					info = les['changes']['caption']
					if 'information' in les['changes'].keys():
						notes = les['changes']['information']
				elif 'information' in les['changes'].keys():
					info = les['changes']['information']

				# new subject?
				if 'newSubjectCode' in les['changes'].keys():
					chgSubject = les['changes']['newSubjectCode']
				
				# new teacher?
				if 'newTeacherCodes' in les['changes'].keys():
					for t in les['changes']['newTeacherCodes']:
						chgTeacher = t
						break
				
				# new room?
				if 'newRoomCodes' in les['changes'].keys():
					for t in les['changes']['newRoomCodes']:
						chgRoom = t
						break
				
				# class missing?
				if 'reasonType' in les['changes'].keys() and les['changes']['reasonType'] == 'classAbsence':
					planType = 2
					chgType = 1
				
				# hour cancelled?
				if 'cancelled' in les['changes'].keys():
					# it was moved!
					if les['changes']['cancelled'] == 'movedAway':
						# it was moved far away. Lets get the details!
						if 'caption' in les['changes'].keys():
							tstMove = pattMovedTo.match(les['changes']['caption'])
							if tstMove is not None:
								day, month, non = tstMove.group(1).split('.')
								weekday = tstMove.group(2)
								mvstr = tstMove.group(3)
								mvend = tstMove.group(5)
								if mvend is not None:
									hourtxt = '%s.-%s.' % (mvstr, mvend)
								else:
									hourtxt = '%s.' % (mvstr,)
								info = ''
								notes = self.config.get('vplan', 'txtMoved').format(weekday, hourtxt, int(day), int(month))

						chgType = 16
					# or the hour is just cancelled.
					elif les['changes']['cancelled'] == 'classFree':
						chgType = 64
						# if the info + notes field is empty, lets populate the field by our own:
						if len(info) == 0 and len(notes) == 0:
							info = self.config.get('vplan', 'txtReplaceFree')

				# date moved from? Then lets get the detail!
				if 'caption' in les['changes'].keys():
					tstMove = pattMovedFrom.match(les['changes']['caption'])
					if tstMove is not None:
						day, month, non = tstMove.group(1).split('.')
						weekday = tstMove.group(2)
						mvstr = tstMove.group(3)
						mvend = tstMove.group(5)
						if mvend is not None:
							hourtxt = '%s.-%s.' % (mvstr, mvend)
						else:
							hourtxt = '%s.' % (mvstr,)
						info = ''
						notes = self.config.get('vplan', 'txtMovedNote').format(weekday, hourtxt, int(day), int(month))
						chgType = 32

				# remove some kind of infos.
				if len(info) > 0:
					if info in self.config.get('vplan', 'rmvInfos').split(';'):
						info = ''

				# now generate the records
				for entryDate in entryDates:
					for className in courses:
						r = {
							'type': planType,
							'date': entryDate,
							'hour': hour,
							'starttime': startTime,
							'endtime': endTime,
							'teacher': teacher,
							'subject': subject,
							'room': room,
							'chgType': chgType,
							'course': className,
							'chgteacher': chgTeacher,
							'chgsubject': chgSubject,
							'chgroom': chgRoom,
							'notes': notes,
							'info': info
						}

						# in case of cancelled class: remove all data!
						if planType == 2:
							r['teacher'] = None
							r['subject'] = None
							r['room'] = None
							r['chgteacher'] = None
							r['chgsubject'] = None
							r['chgroom'] = None
							r['notes'] = ''
							r['hour'] = 0

						exist = False
						# does it already exist there?
						for entry in data['plan']:
							if entry['date'] == r['date'] \
							 and entry['hour'] == r['hour'] \
							 and entry['course'] == r['course'] \
							 and entry['teacher'] == r['teacher'] \
							 and entry['subject'] == r['subject'] \
							 and entry['room'] == r['room']:
								#print('Tried to create a duplicate entry!')
								exist = True
								break

						if not exist:
							data['plan'].append(r)

			f.close()
			self.showToolTip('Neuer Vertretungsplan','Vertretungsplan wurde verarbeitet. Er wird nun hochgeladen.','info')
			self.send_table(data, absPath)
		except Exception as e:
			self.showToolTip('Neuer Vertretungsplan','Vertretungsplan konnte nicht verarbeitet werden. Datei ist fehlerhaft.','error')
			print('Error: %s' % (str(e),))
			raise

	def handlingYardDuty(self, row):
		""" Define a new structure...:
		'type'
		'date'
		'hour'
		'starttime'
		'endtime'
		'teacher'
		'subject'
		'room'
		'course'
		'chgteacher'
		'chgsubject'
		'chgroom'
		'notes'
		'info'
        """

		pattTeacher = re.compile(r'^(((\+([a-zA-ZÄÖÜäöü]+)) )?\(([a-zA-ZÄÖÜäöü]+)\))|([a-zA-ZÄÖÜäöü]+)$')
		r = {
			'type': 4,
			'date': '',
			'hour': None,
			'starttime': None,
			'endtime': None,
			'teacher': None,
			'subject': None,
			'room': None,
			'course': None,
			'chgteacher': None,
			'chgsubject': None,
			'chgroom': None,
			'notes': '',
			'info': ''
		}

		teacherMatch = pattTeacher.match(row[9])
		oldTeacher = None
		newTeacher = None
		if teacherMatch is not None:
			if teacherMatch.group(6) is None:
				newTeacher = teacherMatch.group(4)
				oldTeacher = teacherMatch.group(5)
			else:
				oldTeacher = teacherMatch.group(6)

		# ignore entries, where there is no alternative teacher
		if newTeacher is None:
			return None

		r['date'] = row[3]
		r['teacher'] = oldTeacher
		r['chgteacher'] = newTeacher
		r['notes'] = row[11] 
		# get times
		entryTime = row[7].strip()
		starttime = None
		endtime = None
		if '-' in entryTime:
			starttime, endtime = entryTime.split('-')
			if len(starttime) <= 5:
				starttime = starttime + ':00'
			if len(endtime) <= 5:
				endtime = endtime + ':00'
		r['starttime'] = starttime
		r['endtime'] = endtime

		return r

	def parseRoom(self, sstr, rm):
		'''
		>>> pattRoom.match('+C02, C02, C02 (C14)').groups()
		('+C02, C02, C02 (C14)', '+C02, C02, C02 ', '+C02', 'C02', ', C02', 'C14', None)
		>>> pattRoom.match('C02').groups()
		('C02', None, None, None, None, None, None)
		>>> pattRoom.match('+C02 (C14)').groups()
		('+C02 (C14)', '+C02 ', '+C02', 'C02', None, 'C14', None)
		>>> pattRoom.match('+C02 (C14, C23)').groups()
		('+C02 (C14, C23)', '+C02 ', '+C02', 'C02', None, 'C14', ', C23')
		'''
		newRoom = None
		oldRoom = None

		if rm is not None:
			if '+' not in sstr and rm.group(0) is not None:
				newRoom = rm.group(0).strip()
			elif '+' in sstr:
				# find the right NEW entry.
				for d in rm.groups():
					if d is not None and '+' in d and not d.endswith(' ') \
							and ',' not in d and '(' not in d and ')' not in d:
						newRoom = d.strip().replace('+', '')
						break
				# find the right OLD entry, if it is possible.
				rmgr = []
				for d in rm.groups():
					rmgr.insert(0, d)
				for d in rmgr:
					if d is not None and '+' not in d \
							and ',' not in d and '(' not in d and ')' not in d:
						oldRoom = d.strip()
						break

		return newRoom, oldRoom

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
			self.showToolTip('Neuer Vertretungsplan','Vertretungsplan konnte nicht verarbeitet werden. Datei ist fehlerhaft encodiert.','error')
			return None

		if content is None:
			self.showToolTip('Neuer Vertretungsplan','Vertretungsplan konnte nicht verarbeitet werden. Datei enthält keine Daten.','error')
			return None

		# now decode.
		try:
			jsonDta = json.loads(content)
		except:
			self.showToolTip('Neuer Vertretungsplan','Vertretungsplan konnte nicht verarbeitet werden. Datei ist fehlerhaft.','error')
			return None
		else:
			self.showToolTip('Neuer Vertretungsplan','Vertretungsplan wurde verarbeitet. Er wird nun hochgeladen.','info')
			self.send_table(jsonDta, absPath)

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
