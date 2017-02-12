#!/usr/bin/env python3
# -*- coding: utf8 -*-
# 
# This contains the basic skeleton for creating a 
# parser.
#
# @author Lukas Schreiner
import time
import json
import pprint
import re
from codecs import BOM_UTF8
from planparser.basic import BasicParser, ChangeEntry

class SchoolClassList(object):

	def __init__(self):
		self._list = []

	def append(self, cl):
		self._list.append(cl)

	def remove(self, cl):
		self._list.remove(cl)

	def findClassById(self, cId):
		for f in self._list:
			if f.getId() == cId:
				return f

		return None

	def findClassByAbbreviation(self, abbrev):
		for f in self._list:
			if f.getAbbreviation() == abbrev:
				return f

		return None

	def getList(self):
		return [cl.getAbbreviation() for cl in self._list]

class SchoolClass(object):

	def __init__(self, classId, abbrev):
		self._id = classId
		self._abbreviation = abbrev
		self._team = None

	def setTeam(self, team):
		self._team = team

	def getAbbreviation(self):
		return self._abbreviation

	def getId(self):
		return self._id

	def __str__(self):
		return self._abbreviation

class TeacherList(object):

	def __init__(self):
		self._list = []

	def append(self, cl):
		self._list.append(cl)

	def remove(self, cl):
		self._list.remove(cl)

	def findById(self, cId):
		for f in self._list:
			if f.getId() == cId:
				return f

		return None

	def findByAbbreviation(self, abbrev):
		for f in self._list:
			if f.getAbbreviation() == abbrev:
				return f

		return None

	def getList(self):
		return [cl.getAbbreviation() for cl in self._list]

class Teacher(object):

	def __init__(self, tId, abbrev):
		self._id = tId
		self._abbreviation = abbrev
		self._firstName = None
		self._lastName = None

	def setName(self, firstName, lastName):
		self._firstName = firstName
		self._lastName = lastName

	def getAbbreviation(self):
		return self._abbreviation

	def getId(self):
		return self._id

	def __str__(self):
		return self._abbreviation

class Timetable(object):

	def __init__(self):
		self._list = []

	def append(self, cl):
		self._list.append(cl)

	def remove(self, cl):
		self._list.remove(cl)

	def getMatchingEntries(self, startTime, endTime):
		timeObjects = []

		for to in self._list:
			if to._startTime >= startTime and to._endTime <= endTime:
				timeObjects.append(to._label)

		return timeObjects

class TimeEntry(object):

	def __init__(self, label, start, end):
		self._label = label
		self._startTime = start
		self._endTime = end

	
	def __str__(self):
		return self.__repr__()

	def __repr__(self):
		return '<TimeEntry #%i: %s to %s>' % (self._label, self._startTime, self._endTime)

class DavinciJsonParser(BasicParser):

	def __init__(self, config, errorDialog, parsingFile):
		super().__init__(config, parsingFile)
		self._errorDialog = errorDialog
		self._standin = []
		self._absentClasses = []
		self._absentTeacher = []
		self._supervision = []
		self._classList = SchoolClassList()
		self._teacherList = TeacherList()
		self._stand = None

		# Master data.
		self._timeFramesPupil = Timetable()
		self._timeFramesDuty = Timetable()
		self._teams = {}

		# With the json interface of DaVinci 6, we support mostly all features.
		# So here we set the default flags.
		self._planType = self._planType | BasicParser.PLAN_CANCELED | BasicParser.PLAN_FILLIN
		self._planType = self._planType | BasicParser.PLAN_OUTTEACHER | BasicParser.PLAN_YARDDUTY

	def preParse(self):
		if self._config.has_option('parser-davinci', 'encoding'):
			self._encoding = self._config.get('parser-davinci', 'encoding')
		elif self._encoding is None:
			self._encoding = 'utf-8'

		# check for UTF-8 BOM
		if self._encoding.lower() == 'utf-8' and self._fileContent.startswith(BOM_UTF8):
			self._encoding = 'utf-8-sig'

		try:
			self._fileContent = json.loads(self._fileContent.decode(self._encoding))
		except ValueError:
			raise

		self._stand = int(time.time())
		self.planParserPrepared.emit()

	def parse(self):
		planParsedSuccessful = True
		try:
			self.parseMasterData()
			self.parseAbsentClasses()
			self.parseAbsentTeachers()
			self.parseStandin()
			self.parseYardDuty()
		except Exception as e:
			self._errorDialog.addError('Could not parse the plan. Unexpected error occured: %s.' % (str(e),))
			planParsedSuccessful = False
			raise
		finally:
			self.planParsed.emit(planParsedSuccessful)

	def parseMasterData(self):
		# teams
		for tf in self._fileContent['result']['teams']:
			self._teams[tf['id']] = tf['description']

		# build the class list
		for tf in self._fileContent['result']['classes']:
			schoolClass = SchoolClass(tf['id'], tf['code'])
			if 'teamRefs' in tf:
				for tr in tf['teamRefs']:
					if len(tr) > 0:
						if tr in self._teams.keys():
							schoolClass.setTeam(teams[tr])

			self._classList.append(schoolClass)

		# build the teacher list
		for tf in self._fileContent['result']['teachers']:
			teacher = Teacher(tf['id'], tf['code'])
			if 'firstName' in tf.keys() and 'lastName' in tf.keys():
				teacher.setName(tf['firstName'], tf['lastName'])
			self._teacherList.append(teacher)

		# time frames
		for tf in self._fileContent['result']['timeframes']:
			if tf['code'] in ['Standard', 'Aufsichten']:
				for t in tf['timeslots']:
					te = TimeEntry(int(t['label']), t['startTime'], t['endTime'])
					if tf['code'] == 'Standard':
						self._timeFramesPupil.append(te)
					elif tf['code'] == 'Aufsichten':
						self._timeFramesDuty.append(te)

	def parseAbsentClasses(self):
		# first find the absent classes
		if 'classAbsences' not in self._fileContent.keys():
                    return

		for les in self._fileContent['result']['classAbsences']:
			if les['startDate'] != les['endDate']:
				self._errorDialog.addDebug(
					'Don\'t support different starting and ending date - skipping!',
					pprint.pformat(les)
				)
			elif les['startTime'] != '0000' or les['endTime'] != '0000':
				self._errorDialog.addDebug(
					'Don\'t support start/end time for absent classes - skipping!',
					pprint.pformat(les)
				)
			else:
				entryDate = '%s.%s.%s' % (
					les['startDate'][6:],
					les['startDate'][4:6],
					les['startDate'][:4]
				)

				self._planType = self._planType | BasicParser.PLAN_CANCELED
				newEntry = ChangeEntry([entryDate], 2, None)
				newEntry._hours = [0]
				newEntry._startTime = '00:00:00'
				newEntry._endTime = '23:59:59'
				course = self._classList.findClassById(les['classRef'])
				if course is None:
					self.dlg.addData(pprint.pformat(les))
					self.dlg.addError('Course unknown for absent course - skipping!')
					continue

				newEntry._course = [course]
				self._absentClasses.append(newEntry)

	def parseAbsentTeachers(self):
		# find the absent teachers.
		if 'teacherAbsences' not in self._fileContent.keys():
			return

		for les in self._fileContent['result']['teacherAbsences']:
			if les['startDate'] != les['endDate']:
				self._errorDialog.addDebug(
					'Don\'t support different starting and ending date - skipping!',
					pprint.pformat(les)
				)
			elif les['startTime'] != '0000' or les['endTime'] != '0000':
				self._errorDialog.addDebug(
					'Don\'t support start/end time for absent classes - skipping!',
					pprint.pformat(les)
				)
			else:
				entryDate = '%s.%s.%s' % (
					les['startDate'][6:],
					les['startDate'][4:6],
					les['startDate'][:4]
				)

				self._planType = self._planType | BasicParser.PLAN_OUTTEACHER
				newEntry = ChangeEntry([entryDate], 8, None)
				newEntry._hours = [0]
				newEntry._startTime = '00:00:00'
				newEntry._endTime = '23:59:59'
				teacher = self._teacherList.findById(les['teacherRef'])
				if teacher is None:
					self.dlg.addData(pprint.pformat(les))
					self.dlg.addError('Teacher unknown for absent teachers - skipping!')
					continue

				newEntry._teacher = teacher
				self._absentTeacher.append(newEntry)

	def parseStandin(self):
		# some patterns (better don't ask which possibilities we have).
		pattMovedFrom = re.compile(self._config.get('changekind', 'movedFrom'))
		pattMovedTo = re.compile(self._config.get('changekind', 'movedTo'))

		# find the absent teachers.
		for les in self._fileContent['result']['displaySchedule']['lessonTimes']:
				# skip which don't have changes
				if 'changes' not in les.keys():
					continue

				entryDates = []
				for dt in les['dates']:
					entryDates.append('%s.%s.%s' % (dt[6:], dt[4:6], dt[:4]))

				self._planType = self._planType | BasicParser.PLAN_FILLIN
				newEntry = ChangeEntry(entryDates, 1, None)
				newEntry._startTime = '%s:%s:00' % (les['startTime'][:2], les['startTime'][2:4])
				newEntry._endTime = '%s:%s:00' % (les['endTime'][:2], les['endTime'][2:4])
				newEntry._hours = self._timeFramesPupil.getMatchingEntries(les['startTime'], les['endTime'])
				if len(newEntry._hours) <= 0:
					self._errorDialog.addData(pprint.pformat(les))
					self._errorDialog.addError(
						'Could not find a proper lesson for time: %s to %s - skipping!' % (
							newEntry._startTime,
							newEntry._endTime
						)
					)
					continue

				# now check if the type is classAbsence. In that case, we need to switch to classFree, if the 
				# we have hours given! - otherwise we misinterpret the data.
				if 'reasonType' in les['changes'].keys() and les['changes']['reasonType'] == 'classAbsence' \
					and les['startTime'] != '0000':
					les['changes']['reasonType'] = 'classFree'
					# for FLS, we also need to switch the caption.
					if les['changes']['caption'] == self._config.get('changekind', 'classAbsent'):
						les['changes']['caption'] = self._config.get('vplan', 'txtReplaceFree')

				# in case, there is a special note, we need to inform about the classAbsence reason!
				if 'reasonType' in les['changes'].keys() and les['changes']['reasonType'] in ['classAbsence', 'classFree'] \
					and 'information' not in les['changes'].keys() and 'reasonCode' in les['changes'].keys():
					if 'classAbsenceReasons' in self._fileContent['result'].keys():
						for reason in self._fileContent['result']['classAbsenceReasons']:
							if reason['code'] == les['changes']['reasonCode'] and 'description' in reason.keys():
								les['changes']['information'] = reason['description']
								break

				# subject of course
				try:
					subject = les['subjectCode']
				except KeyError as e:
					# maybe its an additional lesson...?
					if 'lessonTitle' in les['changes'].keys():
						subject = les['changes']['lessonTitle']
					else:
						# is it allowed, if the reasonType == classAbsence!
						if 'reasonType' not in les['changes'].keys() or les['changes']['reasonType'] != 'classAbsence':
							self._errorDialog.addData(pprint.pformat(les))
							self._errorDialog.addWarning(
								'Could not found "subjectCode" (subject) in record - skipping!'
							)
							continue
				newEntry._subject = subject

				# new subject?
				if 'newSubjectCode' in les['changes'].keys():
					newEntry._changeSubject = les['changes']['newSubjectCode']

				# the teacher (strange that it is a list)
				try:
					for t in les['teacherCodes']:
						teacher = t
						break
				except KeyError as e:
					# OK.. lets extract by "absentTeacherCodes" if possible.
					try:
						for t in les['changes']['absentTeacherCodes']:
							teacher = t
							break
					except KeyError as e:
						# is it allowed, if the reasonType == classAbsence!
						if 'reasonType' not in les['changes'].keys() or les['changes']['reasonType'] != 'classAbsence':
							self._errorDialog.addData(pprint.pformat(les))
							self._errorDialog.addWarning('Could not found "teacherCodes" (teacher) in record - skipping!')
							continue
				newEntry._teacher = teacher
				
				# new teacher?
				if 'newTeacherCodes' in les['changes'].keys():
					for t in les['changes']['newTeacherCodes']:
						newEntry._changeTeacher = t
						break

				# Maybe there is no room, but absentRoomCodes; then we have to use this.
				# Changed on 11.11.: absentRoomCodes has the higher priority than the normal room codes.
				if 'absentRoomCodes' in les['changes'].keys() and len(les['changes']['absentRoomCodes']) > 0:
					les['roomCodes'] = les['changes']['absentRoomCodes']

				# Room (we also consider here only the first)
				try:
					for r in les['roomCodes']:
						room = r
						break
				except KeyError as e:
					# is it allowed, if the reasonType == classAbsence!
					if 'reasonType' not in les['changes'].keys() or les['changes']['reasonType'] != 'classAbsence':
						self._errorDialog.addData(pprint.pformat(les))
						self._errorDialog.addWarning('Could not found "roomCodes" (room) in record - skipping!')
						continue
				newEntry._room = room

				# new room?
				if 'newRoomCodes' in les['changes'].keys():
					for t in les['changes']['newRoomCodes']:
						newEntry._changeRoom = t
						break

				# courses
				try:
					for cl in les['classCodes']:
						newEntry._course.append(cl)
				except KeyError:
					self._errorDialog.addData(pprint.pformat(les))
					self._errorDialog.addWarning('Could not found "classCodes" (course) in record - skipping!')
					continue

				# some information?
				if 'caption' in les['changes'].keys():
					newEntry._info = les['changes']['caption']
					if 'information' in les['changes'].keys():
						newEntry._note = les['changes']['information']
				elif 'information' in les['changes'].keys():
					newEntry._info = les['changes']['information']

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
								newEntry._info = ''
								newEntry._note = self._config.get('vplan', 'txtMoved').format(weekday, hourtxt, int(day), int(month))

						chgType = 16
					# or the hour is just cancelled.
					elif les['changes']['cancelled'] == 'classFree':
						chgType = 64
						# if the info + notes field is empty, lets populate the field by our own:
						if len(newEntry._info) == 0 and len(newEntry._note) == 0:
							newEntry._info = self._config.get('vplan', 'txtReplaceFree')

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
						newEntry._info = ''
						newEntry._note = self._config.get('vplan', 'txtMovedNote').format(
							weekday, hourtxt, int(day), int(month)
						)
						chgType = 32

				# remove some kind of infos.
				if len(newEntry._info) > 0:
					if newEntry._info in self._config.get('vplan', 'rmvInfos').split(';'):
						newEntry._info = ''

				lessonRef = None
				try:
					lessonRef = les['lessonRef']
				except KeyError:
					pass

				# a new lesson which replaces an old one but has no reference...
				if lessonRef is None and newEntry._teacher == newEntry._changeTeacher \
					and newEntry._room == newEntry._changeRoom:
					# is the guess algorithm disabled => skip?
					if not self._config.getboolean('options', 'guessOriginalLesson'):
						self._errorDialog.addData(pprint.pformat(les))
						self._errorDialog.addInfo(
							'No lesson reference given and the "guess" algorithm is disabled - skipping!'
						)
						continue

					self._errorDialog.addData(pprint.pformat(les))
					self._errorDialog.addInfo('Found something to guess!')

					# does it already exist there?
					for e in data['plan']:
						if entry['date'] == entryDates[0] \
						 and entry['hour'] == hour \
						 and entry['course'] == courses[0]:
							# found an entry.
							newEntry._teacher = entry['teacher']
							newEntry._room = entry['room']
							if newEntry._subject == '':
								newEntry._subject = entry['subject']
							newEntry._chgType = 0
							break

				self._standin.append(newEntry)

	def parseYardDuty(self):
		# find the absent teachers.
		for les in self._fileContent['result']['displaySchedule']['supervisionTimes']:
				# skip which don't have changes
				if 'changes' not in les.keys():
					continue

				entryDates = []
				for dt in les['dates']:
					entryDates.append('%s.%s.%s' % (dt[6:], dt[4:6], dt[:4]))

				self._planType = self._planType | BasicParser.PLAN_YARDDUTY
				newEntry = ChangeEntry(entryDates, 4, None)
				newEntry._startTime = '%s:%s:00' % (les['startTime'][:2], les['startTime'][2:4])
				newEntry._endTime = '%s:%s:00' % (les['endTime'][:2], les['endTime'][2:4])
				newEntry._hours = self._timeFramesDuty.getMatchingEntries(les['startTime'], les['endTime'])

				# supervisionTitle disabled, because it is modified depending on the change:
				# e.g. Atrium ==> +SCLO (Atrium)
				#if 'supervisionTitle' in les.keys():
				#	newEntry._info = les['supervisionTitle']

				if 'areaCode' in les.keys():
					newEntry._info = les['areaCode']

				oldTeacher = None
				# the teacher (strange that it is a list)
				try:
					for t in les['changes']['absentTeacherCodes']:
						oldTeacher = t
						break
				except KeyError as e:
					# is it allowed, if the reasonType == classAbsence!
					self._errorDialog.addData(pprint.pformat(les))
					self._errorDialog.addWarning('Cannot parse yard change due missing old teacher - skipping!')
					continue

				newTeacher = None
				# the teacher (strange that it is a list)
				try:
					for t in les['teacherCodes']:
						newTeacher = t
						break
				except KeyError as e:
					# is it allowed, if the reasonType == classAbsence!
					self._errorDialog.addData(pprint.pformat(les))
					self._errorDialog.addWarning('Cannot parse yard change due missing new teacher - skipping!')
					continue

				newEntry._teacher = oldTeacher
				newEntry._changeTeacher = newTeacher
				self._supervision.append(newEntry)

	def getResult(self):
		planEntries = []
		planObjects = self._absentClasses + self._absentTeacher + self._supervision + self._standin
		for f in planObjects:
			planEntries.extend(f.asDict())

		return {
			'stand': self._stand,
			'plan': planEntries,
			'ptype': self._planType,
			'class': self._classList.getList()
		}
