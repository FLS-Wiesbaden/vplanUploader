#!/usr/bin/env python3
# -*- coding: utf8 -*-
# 
# This contains the basic skeleton for creating a 
# parser.
#
# @author Lukas Schreiner

from PyQt5.QtCore import QObject, pyqtSignal
import json
import uuid
import hashlib
import bisect

class DuplicateItem(Exception):
	pass

class SuperseedingItem(Exception):
	pass

class SkippedItem(Exception):
	pass

class TimeFrame(object):

	def __init__(self, hour=None, start=None, end=None):
		self.weekday = 0
		self.hour = hour
		self.start = start
		self.end = end

	@property
	def sortkey(self):
		return '{:d}-{:d}'.format(
			self.weekday, self.hour
		)

	def __eq__(self, other):
		return self.weekday == other.weekday and \
			self.hour == other.hour and \
			self.start == other.start and \
			self.end == other.end

	def __lt__(self, other):
		if self.weekday < other.weekday:
			return True
		elif self.weekday > other.weekday:
			return False

		if self.hour < other.hour:
			return True
		elif self.hour > other.hour:
			return False

		if self.start < other.start:
			return True

		return False

	def __gt__(self, other):
		return not self == other and not self < other

	def __str__(self):
		return self.__repr__()

	def __repr__(self):
		return '<TimeFrame #{:d}: {:s} to {:s} on {:d}>'.format(
			self.hour,
			self.start,
			self.end,
			self.weekday
		)

	def toDict(self):
		return {
			'hour': self.hour,
			'start': self.start,
			'end': self.end,
			'weekday': self.weekday
		}

	def serialize(self):
		return self.toDict()

class Timetable(list):

	def __init__(self):
		super().__init__()
		self._keys = []

	def append(self, entry):
		super().append(
			(entry.sortkey, entry)
		)
		self.sort()

	def sort(self):
		super().sort(key=lambda r: r[0])
		self._keys = [ r[0] for r in self ]

	def serialize(self):
		return [ t[1].serialize() for t in self ]

	def find(self, weekday, hour):
		key = '{:d}-{:d}'.format(weekday, hour)
		try:
			res = bisect.bisect_left(self._keys, key)
			return self[res][1]
		except:
			return None

	def findByTime(self, startTime, endTime, weekday=0):
		timeObjects = []
		start = startTime if len(startTime) > 4 else startTime + "00"
		end = endTime if len(endTime) > 4 else endTime + "00"

		for to in self:
			if to.weekday == weekday and \
				to.start >= start and \
				to.end <= end:
				timeObjects.append(to)

		return timeObjects

class Teacher(object):

	def __init__(self, abbreviation=None, firstName=None, lastName=None, teacherId=None):
		self.id = teacherId
		self.abbreviation = abbreviation
		self.firstName = firstName
		self.lastName = lastName

	def __str__(self):
		return self.abbreviation

	def __repr__(self):
		return '<Teacher abbreviation={:s}>'.format(self.abbreviation)

	def serialize(self):
		return {
			'firstname': self.firstName,
			'lastname': self.lastName,
			'abbreviation': self.abbreviation
		}

class Subject(object):
	
	def __init__(self, abbreviation=None, description=None, subjectId=None):
		self.id = subjectId
		self.abbreviation = abbreviation
		self.description = description

	def __str__(self):
		return self.abbreviation

	def __repr__(self):
		return '<Subject abbreviation={:s}>'.format(self.abbreviation)

	def serialize(self):
		return {
			'name': self.description,
			'abbreviation': self.abbreviation
		}

class Room(object):
	
	def __init__(self, abbreviation=None, description=None, roomId=None):
		self.id = roomId
		self.abbreviation = abbreviation
		self.description = description

	def __str__(self):
		return self.abbreviation

	def __repr__(self):
		return '<Room abbreviation={:s}>'.format(self.abbreviation)

	def serialize(self):
		return {
			'name': self.description,
			'abbreviation': self.abbreviation
		}

class SchoolClass(object):
	
	def __init__(self, abbreviation=None, description=None, classId=None, team=None):
		self.id = classId
		self.abbreviation = abbreviation
		self.description = description
		self.team = team

	def __str__(self):
		return self.abbreviation

	def __repr__(self):
		return '<Class abbreviation={:s}>'.format(self.abbreviation)

	def serialize(self):
		return {
			'name': self.description,
			'abbreviation': self.abbreviation
		}

class EntityList(dict):

	def append(self, entry):
		self[entry.abbreviation] = entry

	def remove(self, entry):
		try:
			del(self[entry.abbreviation])
		except:
			pass

	def findById(self, classId):
		for f in self.values():
			if f.id == classId:
				return f

		return None

	def serialize(self):
		return [ cl.serialize() for cl in self.values() ]

class SchoolClassList(EntityList):
	pass

class TeacherList(EntityList):
	pass

class SubjectList(EntityList):
	pass

class RoomList(EntityList):
	pass

class Parser(QObject):

	planFileLoaded = pyqtSignal()
	planParserPrepared = pyqtSignal()
	planParsed = pyqtSignal(bool)

	EXTENSIONS = []

	PLAN_FILLIN = 1
	PLAN_CANCELED = 2
	PLAN_YARDDUTY = 4
	PLAN_OUTTEACHER = 8
	PLAN_ADDITIONAL = 16
	PLAN_REGULAR = 32

	def __init__(self, config, errorDialog, parsingFile):
		super().__init__()
		self._config = config
		self._parsingFile = parsingFile
		self._fileContent = None
		self._planType = 0
		self._encoding = None
		self._errorDialog = errorDialog
		self._stand = None

	def loadFile(self, transaction=None, encoding=None):
		try:
			with open(self._parsingFile, 'rb') as f:
				self._fileContent = f.read()
		except Exception as e:
			if hasattr(self, '_errorDialog'):
				self._errorDialog.addError(
					'Could not parse the new plan with path %s because of %s' % (
						self._parsingFile, str(e)
					)
				)
			self.planParsed(False)
			return

		#self.planFileLoaded.emit()

	def preParse(self, transaction=None):
		self.planParserPrepared.emit()
		pass

	def parse(self, transaction=None):
		self.planParsed(True)
		pass

	def postParse(self, transaction=None):
		pass

	def getResult(self, transaction=None):
		pass

	@staticmethod
	def onlyFirstFile():
		return False

	@staticmethod
	def cknull(data):
		if not data.strip():
			return None
		else:
			return data

	def hasErrors(self):
		if hasattr(self, '_errorDialog'):
			return self._errorDialog.hasData
		else:
			return False

class ChangeEntry(object):

	CHANGE_TYPE_CANCELLED = 1
	CHANGE_TYPE_ROOM = 2
	CHANGE_TYPE_TEACHER = 4
	CHANGE_TYPE_SUBJECT = 8
	CHANGE_TYPE_MOVED = 16
	CHANGE_TYPE_MOVED_FROM = 32
	CHANGE_TYPE_FREE = 64
	CHANGE_TYPE_DUTY = 128
	CHANGE_TYPE_ADD_INFO = 256
	CHANGE_TYPE_TEACHER_AWAY = 512
	CHANGE_TYPE_STANDIN = 1024
	CHANGE_TYPE_REGULAR = 2048

	def __init__(self, dates, planType, chgType = 0):
		self._planType = planType
		self._chgType = chgType
		self._dates = dates
		self._hours = []
		self._startTime = None
		self._endTime = None
		self._teacher = None
		self._subject = None
		self._room = None
		self._course = []
		self._changeTeacher = None
		self._changeSubject = None
		self._changeRoom = None
		self._courseRef = None
		self._note = ''
		self._info = ''

	def hasChanges(self):
		if self._changeTeacher \
			or self._changeSubject \
			or self._changeRoom \
			or self._note \
			or self._info:
			return True
		else:
			return False

	def match(self, dtStr, hour, teacher, subject, room, free=False):
		if dtStr not in self._dates:
			return False

		found = False
		for h in self._hours:
			if h.hour == hour:
				found = True
				break
		if not found:
			return False

		if teacher != self._teacher:
			return False

		if subject != self._subject:
			return False

		if room != self._room:
			return False
			
		if free and not (self._chgType & ChangeEntry.CHANGE_TYPE_FREE) == ChangeEntry.CHANGE_TYPE_FREE:
			return False

		return True
		
	def matchStandin(self, dtStr, hour, teacher, subject, room, free=False):
		if dtStr not in self._dates:
			return False

		found = False
		for h in self._hours:
			if h.hour == hour:
				found = True
				break
		if not found:
			return False

		if self._changeTeacher != None and teacher != self._changeTeacher or \
			self._changeTeacher is None and teacher != self._teacher:
			return False

		if self._changeSubject != None and subject != self._changeSubject or \
			self._changeSubject is None and subject != self._subject:
			return False

		if self._changeRoom != None and room != self._changeRoom or \
			self._changeRoom is None and room != self._room:
			return False

		if free and not (self._chgType & ChangeEntry.CHANGE_TYPE_FREE) == ChangeEntry.CHANGE_TYPE_FREE:
			return False

		return True

	def __lt__(self, other):
		# one of it does not have a date? Bad...
		if not self._dates or not other._dates:
			return False

		# dates
		if self._dates[0] < other._dates[0]:
			return True
		elif self._dates[0] > other._dates[0]:
			return False

		# same day, hour?
		if not self._hours and not other._hours:
			return False
		elif not self._hours:
			return True
		elif not other._hours:
			return False
		elif self._hours[0] < other._hours[0]:
			return True
		elif self._hours[0] > other._hours[0]:
			return False

		# same day, same hour, same room, same class?
		if self._course and other._course and \
			self._course[0] < other._course[0]:
			return True

		return False

	def __eq__(self, other):
		if self._dates == other._dates and \
			self._hours == other._hours and \
			self._course == other._course and \
			self._room == other._room:
			return True
		else:
			return False

	def __gt__(self, other):
		return not self < other and not self == other

	def asDict(self):
		entries = []
		if len(self._course) == 0:
			self._course.append(None)

		for day in self._dates:
			for cour in self._course:
				for tf in self._hours:
					e = {
						'type': self._planType,
						'date': day,
						'hour': tf.hour,
						'starttime': self._startTime if tf.start is None else tf.start,
						'endtime': self._endTime if tf.end is None else tf.end,
						'courseRef': self._courseRef,
						'teacher': str(self._teacher) if self._teacher is not None else None,
						'subject': self._subject,
						'room': self._room,
						'chgType': self._chgType,
						'course': str(cour) if cour is not None else None,
						'chgteacher': str(self._changeTeacher) if self._changeTeacher is not None else None,
						'chgsubject': self._changeSubject,
						'chgroom': self._changeRoom,
						'notes': self._note,
						'info': self._info
					}
					# generate guid
					e['guid'] = str(uuid.UUID(hashlib.blake2s(json.dumps(e).encode('utf-8'), digest_size=16).hexdigest()))
					entries.append(e)

		return entries
