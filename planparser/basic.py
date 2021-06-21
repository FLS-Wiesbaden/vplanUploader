#!/usr/bin/env python3
# -*- coding: utf8 -*-
# 
# This contains the basic skeleton for creating a 
# parser.
#
# @author Lukas Schreiner

from PyQt5.QtCore import QObject, pyqtSignal
import json, uuid, hashlib

class DuplicateItem(Exception):
	pass

class SuperseedingItem(Exception):
	pass

class SkippedItem(Exception):
	pass

class BasicParser(QObject):

	planFileLoaded = pyqtSignal()
	planParserPrepared = pyqtSignal()
	planParsed = pyqtSignal(bool)

	PLAN_FILLIN = 1
	PLAN_CANCELED = 2
	PLAN_YARDDUTY = 4
	PLAN_OUTTEACHER = 8
	PLAN_ADDITIONAL = 16
	PLAN_REGULAR = 32

	def __init__(self, config, parsingFile):
		super().__init__()
		self._config = config
		self._parsingFile = parsingFile
		self._fileContent = None
		self._planType = 0
		self._encoding = None

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
