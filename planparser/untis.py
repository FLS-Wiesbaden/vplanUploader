#!/usr/bin/env python3
# -*- coding: utf8 -*-
# 
# This contains the basic skeleton for creating a 
# parser.
#
# @author Lukas Schreiner
import time
import json
import re
import hashlib
import datetime
import os.path
import datetime
import csv
import bisect
from planparser import basic
from planparser.basic import ChangeEntry

class SchoolClass(basic.SchoolClass):
	
	@classmethod
	def fromList(cls, data):
		return cls(data[0], data[1])

class Room(basic.Room):
	
	@classmethod
	def fromList(cls, data):
		return cls(data[0], data[1])

class Subject(basic.Subject):
	
	@classmethod
	def fromList(cls, data):
		return cls(data[0], data[1])

class Teacher(basic.Teacher):
	
	@classmethod
	def fromList(cls, data):
		return cls(data[0], data[1], data[3])

class PlanDate(object):

	def __init__(self, week, day, date, schoolWeek):
		self.week = week
		self.day = day
		self.date = date
		self.schoolWeek = schoolWeek

	@classmethod
	def fromList(cls, data):
		dt = datetime.datetime.strptime(data[2], '%Y%m%d')
		self = cls(
			int(data[0]),
			data[1],
			dt,
			int(data[3])
		)
		return self

class Lesson(object):

	def __init__(self):
		self.teacher = None
		self.weekday = None
		self.hour = None
		self.subject = None
		self.room = None
		self.untisNumber = None
		self.className = None
		self.weekFlags = '-'*53
		self.flag = 0
		# flag:
		# 0 // default: normaler Unterricht
		# 1 // Unterricht entfällt
		# 2 // Vertretung, Sondereinsatz, ..
		# 3 // Verlegung
		self.lineNumber = 0

	def occur(self, week):
		result = None
		try:
			if self.weekFlags[week-1] in ['1', 'x']:
				result = self.weekFlags[week-1]
		except:
			pass
		finally:
			return result

	def isMainEntry(self):
		return self.flag == 0 or self.flag == 1

	def isCancelledSubentry(self):
		return self.flag == 1 and 'x' in self.weekFlags and not self.className

	@property
	def sortkey(self):
		return '{:d}-{:d}-{:s}-{:d}'.format(
			self.weekday,
			self.hour,
			self.className,
			self.lineNumber
		)

	def generateEntries(self, lessonList, cfg, start, weeks):
		if not self.isMainEntry():
			return None

		generatedWeeks = 0
		curDate = start
		while generatedWeeks < weeks:
			while int(curDate.strftime('%w')) != self.weekday:
				curDate += datetime.timedelta(days=1)

			# does it occur in this week?
			week = int(curDate.strftime('%W'))
			occ = self.occur(week)
			if occ:
				ce = ChangeEntry(
					[curDate.strftime('%d.%m.%Y')],
					0,
				)
				tf = Parser.timeFrames.find(self.weekday, self.hour)
				ce._hours = [tf]
				ce._startTime = tf.start
				ce._endTime = tf.end
				ce._teacher = self.teacher
				ce._subject = self.subject
				ce._room = self.room
				ce._course.append(self.className)
				ce._courseRef = str(self.untisNumber)
				# now check if there is any substitution
				substitutionFound = False
				for les in lessonList.find(self.weekday, self.hour, \
					self.className, self.lineNumber, week, True):
					substitutionFound = True
					ce._planType |= basic.Parser.PLAN_FILLIN
					if self.teacher != les.teacher:
						ce._changeTeacher = les.teacher
						ce._chgType |= ChangeEntry.CHANGE_TYPE_TEACHER
					if self.subject != les.subject:
						ce._changeSubject = les.subject
						ce._chgType |= ChangeEntry.CHANGE_TYPE_SUBJECT
					if self.room != les.room:
						ce._changeRoom = les.room
						ce._chgType |= ChangeEntry.CHANGE_TYPE_ROOM
				if self.flag == 1 or \
					(not substitutionFound and occ == 'x'):
					ce._chgType |= ChangeEntry.CHANGE_TYPE_FREE
					ce._chgType |= ChangeEntry.CHANGE_TYPE_STANDIN
					ce._planType |= basic.Parser.PLAN_FILLIN
					ce._info = cfg.get('vplan', 'txtReplaceFree')
				elif substitutionFound:
					ce._planType |= basic.Parser.PLAN_FILLIN
					ce._chgType |= ChangeEntry.CHANGE_TYPE_STANDIN
				else:
					ce._planType |= basic.Parser.PLAN_REGULAR
					ce._chgType |= ChangeEntry.CHANGE_TYPE_REGULAR
				yield ce
			generatedWeeks += 1
			curDate += datetime.timedelta(days=1)

	@classmethod
	def fromList(cls, data):
		self = cls()
		self.teacher = data[0]
		self.weekday = int(data[1])
		self.hour = int(data[2])
		self.subject = data[3]
		self.room = basic.Parser.cknull(data[4])
		self.untisNumber = int(data[5])
		self.flag = int(data[6])
		self.className = data[7]
		self.weekFlags = data[8]
		self.lineNumber = int(data[9])
		return self

class LessonList(list):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._keys = []

	def append(self, item):
		super().append((item.sortkey, item))

	def sort(self):
		super().sort(key=lambda r: r[0])
		self._keys = [ r[0] for r in self ]

	def merge(self, item):
		for k,les in self:
			if les.weekday == item.weekday and \
				les.hour == item.hour and \
				les.lineNumber == item.lineNumber and \
				les.teacher == item.teacher and \
				les.subject == item.subject and \
				les.flag != item.flag and \
				les.untisNumber == item.untisNumber:
				idx = 0
				while True:
					try:
						idx = item.weekFlags.index('x', idx)
					except ValueError:
						break
					else:
						if les.weekFlags[idx] == '0':
							les.weekFlags = les.weekFlags[:idx] + 'x' + les.weekFlags[idx+1:]
						idx += 1
				break

	def find(self, weekday, hour, className, lineNumber, week=None, \
		skipMainEntry=False):
		key = '{:d}-{:d}-{:s}-{:d}'.format(
			weekday,
			hour,
			className,
			lineNumber
		)
		try:
			res = bisect.bisect_left(self._keys, key)
			while True:
				if not res:
					break

				if self[res][1].weekday != weekday or \
					self[res][1].hour != hour or \
					self[res][1].className != className or \
					self[res][1].lineNumber != lineNumber:
					break

				if skipMainEntry and self[res][1].isMainEntry():
					res += 1
					continue
				elif week and not self[res][1].occur(week):
					res += 1
					continue
				else:
					yield self[res][1]
					res += 1
		except:
			return None

class Substitution(object):

	def __init__(self):
		self.nr = None
		self.type = None
		self.date = None
		self.day = None
		self.hour = None
		self.time = None
		self.subject = None
		self.changeSubject = None
		self.teacher = None
		self.changeTeacher = None
		self.className = None
		self.changeClassName = None
		self.room = None
		self.changeRoom = None
		self.movedInfo = None
		self.notes = None

	def isRelevant(self):
		return self.notes or self.movedInfo

	def getDate(self):
		now = datetime.datetime.now()
		year = now.year
		dt = datetime.datetime.strptime(
			self.date + str(year),
			'%d.%m.%Y'
		)
		if dt < now:
			year += 1
			dt = datetime.datetime.strptime(
				self.date + str(year),
				'%d.%m.%Y'
			)

		return dt

	@classmethod
	def fromList(cls, data):
		self = cls()
		self.nr = int(data[1])
		self.type = basic.Parser.cknull(data[2])
		self.date = basic.Parser.cknull(data[3])
		self.day = basic.Parser.cknull(data[4])
		self.hour = basic.Parser.cknull(data[5])
		self.time = basic.Parser.cknull(data[6])
		self.subject = basic.Parser.cknull(data[7])
		self.changeSubject = basic.Parser.cknull(data[8])
		self.teacher = basic.Parser.cknull(data[9])
		self.changeTeacher = basic.Parser.cknull(data[10])
		self.className = basic.Parser.cknull(data[11])
		self.changeClassName = basic.Parser.cknull(data[12])
		self.room = basic.Parser.cknull(data[13])
		self.changeRoom = basic.Parser.cknull(data[14])
		self.movedInfo = basic.Parser.cknull(data[16])
		self.notes = basic.Parser.cknull(data[21])
		return self

class Supervision(object):

	def __init__(self):
		self.weekday = None
		self.date = None
		self.hour = None
		self.corridor = None
		self.teacher = None
		self.standinTeacher = None
		# Flag: 
		# 0 = base/regular plan
		# 1 = standin for breaks supervision
		# 2 = cancelled supervision
		self.flag = 0

	def isStandin(self):
		return self.flag > 0

	def generateEntry(self):
		ct = basic.ChangeEntry.CHANGE_TYPE_DUTY if self.flag > 0 else 0
		if self.flag == 2:
			ct |= basic.ChangeEntry.CHANGE_TYPE_FREE
		wd = int(self.date.strftime('%w'))
		hourObj = Parser.timeFramesDuty.find(wd, self.hour)
		ce = ChangeEntry([self.date.strftime('%d.%m.%Y')], basic.Parser.PLAN_YARDDUTY, ct)
		ce._hours = [hourObj]
		ce._startTime = hourObj.start
		ce._endTime = hourObj.end
		ce._info = self.corridor
		ce._room = self.corridor
		ce._teacher = self.teacher
		ce._changeTeacher = self.standinTeacher

		return ce

	@classmethod
	def fromList(cls, data):
		self = cls()
		if int(data[5]) == 0:
			self.weekday = int(data[0])
		else:
			self.date = datetime.datetime.strptime(data[0], '%Y%m%d')
		self.hour = int(data[1])
		self.corridor = data[2]
		self.teacher = data[3]
		self.standinTeacher = data[4]
		self.flag = int(data[5])
		return self

class TimeFrame(basic.TimeFrame):

	@classmethod
	def fromList(cls, data):
		self = cls()
		self.weekday = int(data[0])
		self.hour = int(data[1])
		self.start = data[3] + '00'
		self.end = data[4] + '00'
		return self

class Parser(basic.Parser):
	timeFrames: basic.Timetable = None
	timeFramesDuty: basic.Timetable = None

	EXTENSIONS = ['.txt']

	def __init__(self, config, errorDialog, parsingFile):
		super().__init__(config, errorDialog, parsingFile)
		self._planDates = []
		self._standin = []
		self._absentClasses = []
		self._absentTeacher = []
		self._supervision = []
		self._absentDetails = {}
		self._classList = basic.SchoolClassList()
		self._roomList = basic.RoomList()
		self._teacherList = basic.TeacherList()
		self._subjectList = basic.SubjectList()
		self._lessonList = LessonList()
		Parser.timeFrames = basic.Timetable()
		Parser.timeFramesDuty = None

		self._path = os.path.dirname(self._parsingFile)
		self._files = {
			'date.txt': 'parseDates',
			'time.txt': 'parseTimes',
			'class.txt': 'parseClasses',
			'room.txt': 'parseRooms',
			'subject.txt': 'parseSubjects',
			'teacher.txt': 'parseTeachers',
			#'corridor.txt': 'parseCorridor',
			'lesson.txt': 'parseLessons',
			'substitution.txt': 'parseStandin',
			#'student.txt': 'parseStudents',
			'supervision.txt': 'parseSupervisions',
		}
		self._timeout = 10.0

		# With the json interface of DaVinci 6, we support mostly all features.
		# So here we set the default flags.
		self._planType |= basic.Parser.PLAN_CANCELED | basic.Parser.PLAN_FILLIN | basic.Parser.PLAN_REGULAR
		self._planType |= basic.Parser.PLAN_OUTTEACHER | basic.Parser.PLAN_YARDDUTY

	def preParse(self, transaction=None):
		if self._config.has_option('parser-untis', 'encoding'):
			self._encoding = self._config.get('parser-untis', 'encoding')
		elif self._encoding is None:
			self._encoding = 'utf-8'

		self._stand = int(time.time())
		# wait for all files
		self.planParserPrepared.emit()

	def parse(self, transaction=None):
		planParsedSuccessful = True
		# check and verify, all files are available.
		dtstr = datetime.datetime.now()

		found = False
		while (datetime.datetime.now() - dtstr).total_seconds() <= self._timeout:
			found = True
			for fileName in self._files.keys():
				if not os.path.exists(os.path.join(self._path, fileName)):
					found = False
					break

			if not found:
				time.sleep(1)

		if not found:
			raise Exception('Did not got all files required to parse plan within timeout.')

		try:
			for n, f in self._files.items():
				with transaction.start_child(op='parse::untis::%s'.format(f)):
					func = getattr(self, f)
					func(os.path.join(self._path, n))
		except Exception as e:
			self._errorDialog.addError('Could not parse the plan. Unexpected error occured: %s.' % (str(e),))
			planParsedSuccessful = False
			raise
		finally:
			self.planParsed.emit(planParsedSuccessful)

	def parseDates(self, fileName):
		with open(fileName, newline='', encoding=self._encoding) as csvfile:
			reader = csv.reader(csvfile, delimiter='\t', quoting=csv.QUOTE_NONE)
			for row in reader:
				pd = PlanDate.fromList(row)
				self._planDates.append(pd)

	def parseTimes(self, fileName):
		with open(fileName, newline='', encoding=self._encoding) as csvfile:
			reader = csv.reader(csvfile, delimiter='\t', quoting=csv.QUOTE_NONE)
			for row in reader:
				pd = TimeFrame.fromList(row)
				Parser.timeFrames.append(pd)

		# generate yard duties times.
		Parser.timeFramesDuty = Parser.timeFrames.generateYardduties(Parser.timeFrames)

	def parseClasses(self, fileName):
		with open(fileName, newline='', encoding=self._encoding) as csvfile:
			reader = csv.reader(csvfile, delimiter='\t', quoting=csv.QUOTE_NONE)
			for row in reader:
				self._classList.append(SchoolClass.fromList(row))

	def parseRooms(self, fileName):
		with open(fileName, newline='', encoding=self._encoding) as csvfile:
			reader = csv.reader(csvfile, delimiter='\t', quoting=csv.QUOTE_NONE)
			for row in reader:
				self._roomList.append(Room.fromList(row))

	def parseSubjects(self, fileName):
		with open(fileName, newline='', encoding=self._encoding) as csvfile:
			reader = csv.reader(csvfile, delimiter='\t', quoting=csv.QUOTE_NONE)
			for row in reader:
				self._subjectList.append(Subject.fromList(row))

	def parseTeachers(self, fileName):
		with open(fileName, newline='', encoding=self._encoding) as csvfile:
			reader = csv.reader(csvfile, delimiter='\t', quoting=csv.QUOTE_NONE)
			for row in reader:
				self._teacherList.append(Teacher.fromList(row))

	def parseLessons(self, fileName):
		with open(fileName, newline='', encoding=self._encoding) as csvfile:
			reader = csv.reader(csvfile, delimiter='\t', quoting=csv.QUOTE_NONE)
			for row in reader:
				pd = Lesson.fromList(row)
				if not pd.isCancelledSubentry():
					self._lessonList.append(pd)
				else:
					# find and merge the right one.
					self._lessonList.merge(pd)

		self._lessonList.sort()
		dt = datetime.datetime.now()
		genWeeks = 2
		try:
			genWeeks = int(self._config.get('parser-untis', 'weeks'))
		except ValueError:
			pass
		for key, lesson in self._lessonList:
			for x in lesson.generateEntries(self._lessonList, self._config, dt, genWeeks):
				self._standin.append(x)

		self._standin.sort()
		
		hf = {}
		for x in self._standin:
			sk = '{:s}-{:s}'.format(
				x._dates[0],
				x._course[0]
			)
			if not (x._chgType & ChangeEntry.CHANGE_TYPE_FREE) == ChangeEntry.CHANGE_TYPE_FREE and \
				not (x._chgType & ChangeEntry.CHANGE_TYPE_CANCELLED) == ChangeEntry.CHANGE_TYPE_CANCELLED:
				add = 1
			else:
				add = 0
			try:
				hf[sk] += add
			except KeyError:
				hf[sk] = add

		for k,v in hf.items():
			if v == 0:
				dt, cn = k.split('-', 1)
				ce = ChangeEntry([dt], basic.Parser.PLAN_CANCELED, ChangeEntry.CHANGE_TYPE_CANCELLED)
				ce._course = [cn]
				ce._hours = [basic.TimeFrame(
					hour=0,
					start='000000',
					end='235959'
				)]
				self._absentClasses.append(ce)

	def parseSupervisions(self, fileName):
		with open(fileName, newline='', encoding=self._encoding) as csvfile:
			reader = csv.reader(csvfile, delimiter='\t', quoting=csv.QUOTE_NONE)
			for row in reader:
				pd = Supervision.fromList(row)
				if pd.isStandin():
					self._supervision.append(pd.generateEntry())

	def parseStandin(self, fileName):
		"""Parses file "substitution.txt"

		Args:
			fileName (str): Path incl. filename to the substitution.txt

		The data is parsed into Substitution class. Result is e.g.:

		Type: **Moved**
		{'nr': 54, 'type': 'Verlegung', 'date': '25.6.', 'day': 'Fr', 'hour': '8', 'time': '14:15-15:00', 
		'subject': 'SPD', 'changeSubject': 'SPD', 'teacher': 'KETZ', 'changeTeacher': 'KETZ', 'className': '1192', 
		'changeClassName': '1192', 'room': 'A107 DV', 'changeRoom': 'A107 DV', 'movedInfo': 'Do-24.6. / 6', 'notes': None}

		Type: **Standin**
		{'nr': 48, 'type': 'Vertretung', 'date': '23.6.', 'day': 'Mi', 'hour': '2', 'time': '8:45-9:30', 'subject': 'MATH', 
		'changeSubject': 'MATH', 'teacher': 'HOFM', 'changeTeacher': 'BERM', 'className': '1181', 'changeClassName': '1181', 
		'room': 'C12', 'changeRoom': 'C12', 'movedInfo': None, 'notes': 'Aufgabenstellung in moodle bearbeiten'}

		Type: **Cancelled/Free**
		{'nr': 4, 'type': 'Entfall', 'date': '22.6.', 'day': 'Di', 'hour': '5', 'time': '11:30-12:15', 'subject': 'INFO', 
		'changeSubject': "'---", 'teacher': 'SCLO', 'changeTeacher': "'---", 'className': '12', 'changeClassName': '12', 
		'room': None, 'changeRoom': "'---", 'movedInfo': None, 'notes': 'Aufgabenstellung in moodle bearbeiten'}

		Its important, that the lessons are parsed before. In this case, we can /easily/ find the standin information
		and add soem further texts...
		"""
		substList = []
		with open(fileName, newline='', encoding=self._encoding) as csvfile:
			reader = csv.reader(csvfile, delimiter='\t', quoting=csv.QUOTE_NONE)
			for row in reader:
				if row[0] == 'VTD':
					pd = Substitution.fromList(row)
					# skip entries not relevant.
					if pd.isRelevant():
						substList.append(pd)
		
		# check every substitution whether we have notes we must attach.
		# FIXME: validate better option. As per last test file of FLS,
		# the "to" can be retrieved from column R and "from" of column Q
		now = datetime.datetime.now()
		for sub in substList:
			dt = sub.getDate()
			dtStr = dt.strftime('%d.%m.%Y')
			dtStrMoved = None
			if sub.movedInfo:
				tstMove = re.match('^([a-zA-Z]{2,3})\-([0-9]{1,2})\.([0-9]{1,2})\.\s\/\s([0-9])$', sub.movedInfo)
				if tstMove:
					weekday = tstMove.group(1)
					hourtxt = tstMove.group(4)
					day = int(tstMove.group(2))
					month = int(tstMove.group(3))
					# day now/current
					a1 = datetime.datetime(dt.year, month, day)
					if a1 < dt:
						a1 = dt-a1
					else:
						a1 = a1-dt
					a2 = datetime.datetime(dt.year+1, month, day)-dt
					a3 = dt-datetime.datetime(dt.year-1, month, day)
					a = min(a1, a2, a3)
					dtChk = None
					if a == a1:
						dtChk = datetime.datetime(dt.year, month, day)
					elif a == a2:
						dtChk = datetime.datetime(dt.year+1, month, day)
					else:
						dtChk = datetime.datetime(dt.year-1, month, day)
					
					dtStrMoved = dtChk.strftime('%d.%m.%Y')
				else:
					# skip entry if not usable.
					continue
			
			if sub.notes:
				for les in self._standin:
					# this is the later entry, we should find first!
					if les.match(dtStr, int(sub.hour), sub.teacher, sub.subject, sub.room):
						if sub.notes:
							les._note = sub.notes
							break
					
			# its a move. Link each other! Find the original one.
			if sub.movedInfo:
				for les in self._standin:
					# find the standin
					if les.matchStandin(dtStr, int(sub.hour), sub.teacher, sub.subject, sub.room):
						foundOles = False
						for oles in self._standin:
							if oles.match(dtStrMoved, int(hourtxt), sub.teacher, sub.subject, sub.room, free=True):
								dtr = datetime.datetime.strptime(les._dates[0], '%d.%m.%Y')
								weekday = dtr.strftime('%a')
								hourtxt = str(les._hours[0].hour) + '.'
								day = dtr.strftime('%d')
								month = dtr.strftime('%m')
								oles._note = self._config.get('vplan', 'txtMoved').format(
									weekday, hourtxt, int(day), int(month)
								)
								oles._chgType |= ChangeEntry.CHANGE_TYPE_MOVED_FROM
								foundOles = True
								break

						weekday = tstMove.group(1)
						hourtxt = str(tstMove.group(4)) + '.'
						day = tstMove.group(2)
						month = tstMove.group(3)
						les._note = self._config.get('vplan', 'txtMovedNote').format(
							weekday, hourtxt, int(day), int(month)
						)
						les._chgType |= ChangeEntry.CHANGE_TYPE_MOVED
						break

	def getResult(self, transaction=None):
		planEntries = []
		planObjects = self._absentClasses + self._absentTeacher + self._supervision + self._standin
		for f in planObjects:
			planEntries.extend(f.asDict())

		encClasses = self._classList.serialize()
		encTeachers = self._teacherList.serialize()
		encSubjects = self._subjectList.serialize()
		encRooms = self._roomList.serialize()
		encTimeframes = Parser.timeFrames.serialize()
		encTimeframesDuty = Parser.timeFramesDuty.serialize()
		return {
			'stand': self._stand,
			'plan': planEntries,
			'ptype': self._planType,
			'class': encClasses,
			'teacher': encTeachers,
			'subjects': encSubjects,
			'rooms': encRooms,
			'timeframes': {
				'pupil': encTimeframes,
				'duty': encTimeframesDuty
			},
			'hashes': {
				'pupil': hashlib.sha256(json.dumps(encTimeframes).encode('utf-8')).hexdigest(),
				'duty': hashlib.sha256(json.dumps(encTimeframesDuty).encode('utf-8')).hexdigest(),
				'classes': hashlib.sha256(json.dumps(encClasses).encode('utf-8')).hexdigest(),
				'teacher': hashlib.sha256(json.dumps(encTeachers).encode('utf-8')).hexdigest(),
				'subjects': hashlib.sha256(json.dumps(encSubjects).encode('utf-8')).hexdigest(),
				'rooms': hashlib.sha256(json.dumps(encRooms).encode('utf-8')).hexdigest()
			}
		}

	@staticmethod
	def onlyFirstFile():
		return True
