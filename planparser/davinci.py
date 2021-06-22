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
import hashlib
import datetime
from codecs import BOM_UTF8
from planparser import basic
from planparser.basic import BasicParser, ChangeEntry
from planparser.basic import DuplicateItem, SuperseedingItem, SkippedItem

class SchoolClassList(object):

	def __init__(self):
		self._list = []
		self._idx = {}

	def append(self, cl):
		self._list.append(cl)
		self._idx[cl.getAbbreviation()] = cl

	def remove(self, cl):
		self._list.remove(cl)
		try:
			del(self._idx[cl.getAbbreviation()])
		except:
			pass

	def findClassById(self, cId):
		for f in self._list:
			if f.getId() == cId:
				return f

		return None

	def findClassByAbbreviation(self, abbrev):
		try:
			return self._idx[abbrev]
		except KeyError:
			return None

	def getList(self):
		return list(self._idx.keys())

class SchoolClass(object):

	def __init__(self, classId, abbrev):
		self._id = classId
		self._abbreviation = abbrev
		self._team = None
		self._description = None

	def setTeam(self, team):
		self._team = team

	def setDescription(self, desc):
		self._description = desc

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

	def serialize(self):
		return [cl.serialize() for cl in self._list]

class SubjectList(object):

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

	def serialize(self):
		return [cl.serialize() for cl in self._list]

class TimeFrame(basic.TimeFrame):

	@classmethod
	def fromJson(cls, data):
		self = cls()
		self.hour = int(data['label'])
		self.start = data['startTime'] + "00"
		self.end = data['endTime'] + "00"
		return self

class ClassAbsentReason(object):

	def __init__(self, code, id, description=None, color=None):
		self._code = code
		self._color = color
		self._id = id
		self._description = description

	def getId(self):
		return self._id

	def getDescription(self):
		return self._description

	def __str__(self):
		return self.__repr__()

	def __repr__(self) -> str:
		return '<ClassAbsentReason: %s to %s>' % (self._code, self._id)

	def serialize(self):
		return {
			'code': self._code,
			'color': self._color,
			'id': self._id,
			'description': self._description
		}

	@classmethod
	def fromJson(cls, data):
		self = cls(
			data['code'],
			data['id'],
			data['description'] if 'description' in data.keys() else None,
			data['color'] if 'color' in data.keys() else None
		)
		return self

class DavinciJsonParser(BasicParser):

	def __init__(self, config, errorDialog, parsingFile):
		super().__init__(config, parsingFile)
		self._errorDialog = errorDialog
		self._standin = []
		self._absentClasses = []
		self._absentTeacher = []
		self._supervision = []
		self._absentDetails = {}
		self._classList = SchoolClassList()
		self._teacherList = TeacherList()
		self._subjectList = SubjectList()
		self._stand = None

		# Master data.
		self._timeFramesPupil = basic.Timetable()
		self._timeFramesDuty = basic.Timetable()
		self._classAbsentReasons = {}
		self._teams = {}

		# With the json interface of DaVinci 6, we support mostly all features.
		# So here we set the default flags.
		self._planType = self._planType | BasicParser.PLAN_CANCELED | BasicParser.PLAN_FILLIN
		self._planType = self._planType | BasicParser.PLAN_OUTTEACHER | BasicParser.PLAN_YARDDUTY

		# some patterns (better don't ask which possibilities we have).
		self._pattMovedFrom = re.compile(self._config.get('changekind', 'movedFrom'))
		self._pattMovedTo = re.compile(self._config.get('changekind', 'movedTo'))

	def preParse(self, transaction=None):
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

	def parse(self, transaction=None):
		planParsedSuccessful = True
		try:
			with transaction.start_child(op='parse::davinci::parseMasterData'):
				self.parseMasterData()
			
			with transaction.start_child(op='parse::davinci::parseAbsentClasses'):
				self.parseAbsentClasses()
			with transaction.start_child(op='parse::davinci::parseAbsentTeachers'):
				self.parseAbsentTeachers()
			with transaction.start_child(op='parse::davinci::parseStandin'):
				self.parseStandin()
			if 'supervisionTimes' in self._fileContent['result']['displaySchedule'].keys():
				with transaction.start_child(op='parse::davinci::parseYardDuty'):
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
			if 'description' in tf.keys():
				schoolClass.setDescription(tf['description'])
			if 'teamRefs' in tf:
				for tr in tf['teamRefs']:
					if len(tr) > 0:
						if tr in self._teams.keys():
							schoolClass.setTeam(self._teams[tr])

			self._classList.append(schoolClass)

		# build the teacher list
		for tf in self._fileContent['result']['teachers']:
			teacher = basic.Teacher(teacherId=tf['id'], abbreviation=tf['code'])
			if 'firstName' in tf.keys() and 'lastName' in tf.keys():
				teacher.firstName = tf['firstName']
				teacher.lastName = tf['lastName']
			self._teacherList.append(teacher)


		# build the subject list
		for tf in self._fileContent['result']['subjects']:
			subject = basic.Subject(subjectId=tf['id'], abbreviation=tf['code'])
			if 'description' in tf.keys():
				subject.description = tf['description']
			self._subjectList.append(subject)

		# time frames
		for tf in self._fileContent['result']['timeframes']:
			if tf['code'] in ['Standard', 'Aufsichten']:
				for t in tf['timeslots']:
					te = TimeFrame.fromJson(t)
					if tf['code'] == 'Standard':
						self._timeFramesPupil.append(te)
					elif tf['code'] == 'Aufsichten':
						self._timeFramesDuty.append(te)

		# class absent reason
		if 'classAbsenceReasons' in self._fileContent['result'].keys():
			for tf in self._fileContent['result']['classAbsenceReasons']:
				self._classAbsentReasons[tf['code']] = ClassAbsentReason.fromJson(tf)

	def parseAbsentClasses(self):
		# FIXME: Check for weekday Saturday/Sunday
		# first find the absent classes
		if 'classAbsences' not in self._fileContent['result'].keys():
			return

		for les in self._fileContent['result']['classAbsences']:
			# save for later.
			hashKey = '{}{}'.format(
				les['classRef'], les['reasonRef']
			)
			if hashKey not in self._absentDetails.keys():
				self._absentDetails[hashKey] = [les]
			else:
				self._absentDetails[hashKey].append(les)
			# we do not support separate absent classes here for a 
			# time period less than a day.
			if les['startTime'] != '0000' or les['endTime'] != '0000':
				self._errorDialog.addDebug(
					'Don\'t support start/end time for absent classes - skipping!',
					pprint.pformat(les)
				)
			else:
				# iterate through dates
				absentStart = datetime.datetime.strptime(
					'{}{}'.format(les['startDate'], les['startTime']), 
					'%Y%m%d%H%M'
				)
				absentEnd = datetime.datetime.strptime(
					'{}{}'.format(les['endDate'], les['endTime']), 
					'%Y%m%d%H%M'
				)

				while absentStart < absentEnd:
					entryDate = absentStart.strftime('%d.%m.%Y')

					self._planType = self._planType | BasicParser.PLAN_CANCELED
					newEntry = ChangeEntry([entryDate], 2, ChangeEntry.CHANGE_TYPE_CANCELLED)
					newEntry._hours = [{
						'hour': 0,
						'start': '000000',
						'end': '235959'
					}]
					newEntry._startTime = '00:00:00'
					newEntry._endTime = '23:59:59'
					course = self._classList.findClassById(les['classRef'])
					if course is None:
						self.dlg.addData(pprint.pformat(les))
						self.dlg.addError('Course unknown for absent course - skipping!')
						continue

					newEntry._course = [course]
					newEntry._reasonRef = les['reasonRef']
					try:
						newEntry._note = les['note']
					except:
						pass
					self._absentClasses.append(newEntry)

					absentStart += datetime.timedelta(days=1)

	def parseAbsentTeachers(self):
		# find the absent teachers.
		if 'teacherAbsences' not in self._fileContent.keys():
			return

		for les in self._fileContent['result']['teacherAbsences']:
			if les['startTime'] != '0000' or les['endTime'] != '0000':
				self._errorDialog.addDebug(
					'Don\'t support start/end time for absent classes - skipping!',
					pprint.pformat(les)
				)
			else:
				# iterate through dates
				absentStart = datetime.datetime.strptime(
					'{}{}'.format(les['startDate'], les['startTime']), 
					'%Y%m%d%H%M'
				)
				absentEnd = datetime.datetime.strptime(
					'{}{}'.format(les['endDate'], les['startTime']), 
					'%Y%m%d%H%M'
				)

				while absentStart <= absentEnd:
					entryDate = absentStart.strftime('%d.%m.%Y')

					self._planType = self._planType | BasicParser.PLAN_OUTTEACHER
					newEntry = ChangeEntry([entryDate], 8, ChangeEntry.CHANGE_TYPE_TEACHER_AWAY)
					newEntry._hours = [basic.TimeFrame(
						hour=0,
						start='000000',
						end='235959'
					)]
					newEntry._startTime = '00:00:00'
					newEntry._endTime = '23:59:59'
					teacher = self._teacherList.findById(les['teacherRef'])
					if teacher is None:
						self.dlg.addData(pprint.pformat(les))
						self.dlg.addError('Teacher unknown for absent teachers - skipping!')
						continue

					newEntry._teacher = teacher
					newEntry._reasonRef = les['reasonRef']
					try:
						newEntry._note = les['note']
					except:
						pass
					self._absentTeacher.append(newEntry)

					absentStart += datetime.timedelta(days=1)

	def _parseChanges(self, les, newEntry):
		self._planType = self._planType | BasicParser.PLAN_FILLIN

		# substitution cancelled? 
		if 'cancelled' in les['changes'].keys() and les['changes']['cancelled'] == 'substitutionCancelled':
			self._errorDialog.addData(pprint.pformat(les))
			self._errorDialog.addWarning('Found entry which has a cancelled substitution (changes of a change?).')
			raise SuperseedingItem()

		# new subject?
		if 'newSubjectCode' in les['changes'].keys():
			newEntry._changeSubject = les['changes']['newSubjectCode']
			newEntry._chgType |= ChangeEntry.CHANGE_TYPE_SUBJECT

		# new teacher?
		if 'newTeacherCodes' in les['changes'].keys():
			for t in les['changes']['newTeacherCodes']:
				newEntry._changeTeacher = t
				newEntry._chgType |= ChangeEntry.CHANGE_TYPE_TEACHER
				break

		# new room?
		if 'newRoomCodes' in les['changes'].keys():
			for t in les['changes']['newRoomCodes']:
				newEntry._changeRoom = t
				newEntry._chgType |= ChangeEntry.CHANGE_TYPE_ROOM
				break

		# now check if the type is classAbsence. In that case, we need to switch to classFree, if the 
		# we have hours given! - otherwise we misinterpret the data.
		if 'reasonType' in les['changes'].keys() and les['changes']['reasonType'] == 'classAbsence' \
			and les['startTime'] != '0000':
			les['changes']['reasonType'] = 'classFree'
			# for FLS, we also need to switch the caption.
			if 'caption' in les['changes'].keys() and \
				les['changes']['caption'] == self._config.get('changekind', 'classAbsent'):
				les['changes']['caption'] = self._config.get('vplan', 'txtReplaceFree')

		# in case, there is a special note, we need to inform about the classAbsence reason!
		if 'reasonType' in les['changes'].keys() and les['changes']['reasonType'] in ['classAbsence', 'classFree'] \
			and 'information' not in les['changes'].keys() and 'reasonCode' in les['changes'].keys():
			try:
				absentReasonObj = self._classAbsentReasons[les['changes']['reasonCode']]
			except KeyError:
				pass
			else:
				if absentReasonObj.getDescription():
					les['changes']['information'] = absentReasonObj.getDescription()
				elif les['classCodes']:
					# last try, through the details.
					# get first class code
					classObj = self._classList.findClassByAbbreviation(les['classCodes'][0])
					if classObj and not newEntry._note:
						reason = self.findAbsentReason(classObj.getId(), absentReasonObj.getId(), les)
						if reason:
							newEntry._note = reason

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
					tstMove = self._pattMovedTo.match(les['changes']['caption'])
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

				newEntry._chgType |= ChangeEntry.CHANGE_TYPE_MOVED
			# or the hour is just cancelled.
			elif les['changes']['cancelled'] == 'classFree':
				newEntry._chgType |= ChangeEntry.CHANGE_TYPE_FREE
				# if the info + notes field is empty, lets populate the field by our own:
				if len(newEntry._info) == 0 and len(newEntry._note) == 0:
					newEntry._info = self._config.get('vplan', 'txtReplaceFree')

		# date moved from? Then lets get the detail!
		if 'caption' in les['changes'].keys():
			tstMove = self._pattMovedFrom.match(les['changes']['caption'])
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
				newEntry._chgType |= ChangeEntry.CHANGE_TYPE_MOVED_FROM

		# if a change type is set to 6 = free and we do not have any
		# change type defined yet, take it!
		if not newEntry._chgType and 'changeType' in les['changes'] and les['changes']['changeType'] == 6:
			newEntry._chgType |= ChangeEntry.CHANGE_TYPE_FREE
			# if the info + notes field is empty, lets populate the field by our own:
			if not newEntry._info and not newEntry._note:
				newEntry._info = self._config.get('vplan', 'txtReplaceFree')

		# in certain situation it may happen, that we misinterpret some data and 
		# that the standin found does not contain any changes. This is strange and should be
		# marked somehow!
		if not newEntry.hasChanges():
			self._errorDialog.addData(pprint.pformat(les))
			self._errorDialog.addInfo(
				'Found changes which is not understandable (no changes !?) - assume is fine.'
			)

		return newEntry

	def _parseLesson(self, les):
		# now also those hurdles accomplished. Next one is knocking at the door. 
		# Check if there is an similiar entry as this one which superseeds it.
		# E.g. this here is a room change. And there is one which just moves the complete hour away.
		# But we need to do it only if this changeType is "0".
		if 'changes' in les.keys() and \
			'changeType' in les['changes'] and \
			les['changes']['changeType'] > 0 and \
			'lessonRef' in les.keys():
			mainkey = {
				'classCodes': les['classCodes'] if 'classCodes' in les.keys() else [],
				'roomCodes': les['roomCodes'] if 'roomCodes' in les.keys() else [],
				'teacherCodes': les['teacherCodes'] if 'teacherCodes' in les.keys() else []
			}
			mainhash = hashlib.sha256(json.dumps(mainkey, sort_keys=True).encode('utf-8')).hexdigest()
			skip = False
			for subles in self._fileContent['result']['displaySchedule']['lessonTimes']:
				# skip which don't have changes
				if 'changes' not in subles.keys():
					continue
				# skip those which do not have same key
				if 'lessonRef' not in subles.keys() or \
					subles['lessonRef'] != les['lessonRef'] or \
					subles['courseRef'] != les['courseRef'] or \
					subles['startTime'] != les['startTime'] or \
					subles['dates'] != les['dates'] or \
					'roomCodes' not in subles.keys() or \
					'teacherCodes' not in subles.keys() or \
					'classCodes' not in subles.keys() or \
					'changeType' not in subles['changes']:
					continue
				subkey = {
					'classCodes': subles['classCodes'],
					'roomCodes': subles['roomCodes'],
					'teacherCodes': subles['teacherCodes']
				}
				subhash = hashlib.sha256(json.dumps(subkey, sort_keys=True).encode('utf-8')).hexdigest()
				if subhash != mainhash:
					continue
				elif subles['changes']['changeType'] == 0:
					skip = True
					break

			if skip:
				self._errorDialog.addData(pprint.pformat(les))
				self._errorDialog.addWarning('Skipped, seems there is a superseeding entry!')
				raise SuperseedingItem()

		# parse regular information
		entryDates = []
		try:
			for dt in les['dates']:
				entryDates.append('%s.%s.%s' % (dt[6:], dt[4:6], dt[:4]))
		except KeyError:
			self._errorDialog.addData(pprint.pformat(les))
			self._errorDialog.addError('Found a record without any valid applicable date!')
			raise SkippedItem()

		newEntry = ChangeEntry(entryDates, 1)
		newEntry._startTime = '%s:%s:00' % (les['startTime'][:2], les['startTime'][2:4])
		newEntry._endTime = '%s:%s:00' % (les['endTime'][:2], les['endTime'][2:4])
		newEntry._hours = self._timeFramesPupil.findByTime(les['startTime'], les['endTime'])
		newEntry._courseRef = les['courseRef']
		if len(newEntry._hours) <= 0:
			self._errorDialog.addData(pprint.pformat(les))
			self._errorDialog.addError(
				'Could not find a proper lesson for time: %s to %s - skipping!' % (
					newEntry._startTime,
					newEntry._endTime
				)
			)
			raise SkippedItem()

		# subject of course
		try:
			newEntry._subject = les['subjectCode']
		except KeyError as e:
			# maybe its an additional lesson...?
			try:
				newEntry._subject = les['changes']['lessonTitle']
			except KeyError:
				# is it allowed, if the reasonType == classAbsence!
				if 'changes' not in les.keys() or \
					'reasonType' not in les['changes'].keys() or \
					les['changes']['reasonType'] != 'classAbsence':
					self._errorDialog.addData(pprint.pformat(les))
					self._errorDialog.addWarning(
						'Could not found "subjectCode" (subject) in record - skipping!'
					)
					raise SkippedItem()

		# the teacher (strange that it is a list)
		try:
			for t in les['teacherCodes']:
				newEntry._teacher = t
				break
		except KeyError as e:
			# OK.. lets extract by "absentTeacherCodes" if possible.
			try:
				for t in les['changes']['absentTeacherCodes']:
					newEntry._teacher = t
					break
			except KeyError as e:
				# is it allowed, if the reasonType == classAbsence!
				if 'changes' not in les.keys() or \
					'reasonType' not in les['changes'].keys() or \
					les['changes']['reasonType'] != 'classAbsence':
					self._errorDialog.addData(pprint.pformat(les))
					self._errorDialog.addWarning('Could not found "teacherCodes" (teacher) in record - skipping!')
					raise SkippedItem()

		# Maybe there is no room, but absentRoomCodes; then we have to use this.
		# Changed on 11.11.: absentRoomCodes has the higher priority than the normal room codes.
		if 'changes' in les.keys() and \
			'absentRoomCodes' in les['changes'].keys() and len(les['changes']['absentRoomCodes']) > 0:
			les['roomCodes'] = les['changes']['absentRoomCodes']

		# Room (we also consider here only the first)
		try:
			for r in les['roomCodes']:
				newEntry._room = r
				break
		except KeyError as e:
			# is it allowed, if the reasonType == classAbsence!
			if 'changes' not in les.keys() or \
				'reasonType' not in les['changes'].keys() or les['changes']['reasonType'] != 'classAbsence':
				# in pandemic times, with much remote works, it is valid, that rooms are not present.
				#self._errorDialog.addData(pprint.pformat(les))
				#self._errorDialog.addWarning('Could not found "roomCodes" (room) in record - skipping!')
				#noSkipped += 1
				#continue
				newEntry._room = ''

		# courses
		try:
			for cl in les['classCodes']:
				newEntry._course.append(cl)
		except KeyError:
			self._errorDialog.addData(pprint.pformat(les))
			self._errorDialog.addWarning('Could not found "classCodes" (course) in record - skipping!')
			raise SkippedItem()

		lessonRef = None
		try:
			lessonRef = les['lessonRef']
		except KeyError:
			pass

		# parse changes if applicable.
		# skip which don't have changes
		if 'changes' in les.keys():
			newEntry = self._parseChanges(les, newEntry)
			newEntry._planType = BasicParser.PLAN_FILLIN
			newEntry._chgType |= ChangeEntry.CHANGE_TYPE_STANDIN
		else:
			self._planType = self._planType | BasicParser.PLAN_REGULAR
			newEntry._planType = BasicParser.PLAN_REGULAR
			newEntry._chgType |= ChangeEntry.CHANGE_TYPE_REGULAR

		# remove some kind of infos.
		if len(newEntry._info) > 0:
			if newEntry._info in self._config.get('vplan', 'rmvInfos').split(';'):
				newEntry._info = ''

		# a new lesson which replaces an old one but has no reference...
		if lessonRef is None and newEntry._teacher == newEntry._changeTeacher \
			and newEntry._room == newEntry._changeRoom:
			# is the guess algorithm disabled => skip?
			if not self._config.getboolean('options', 'guessOriginalLesson'):
				self._errorDialog.addData(pprint.pformat(les))
				self._errorDialog.addInfo(
					'No lesson reference given and the "guess" algorithm is disabled - skipping!'
				)
				raise SkippedItem()

			self._errorDialog.addData(pprint.pformat(les))
			self._errorDialog.addInfo('Found something to guess!')

		self._standin.append(newEntry)

	def parseStandin(self):
		duplicateLes = []
		noDuplicates = 0
		noSkipped = 0
		noSuperseeding = 0
		concurrentItems = {}

		# find the absent teachers.
		for les in self._fileContent['result']['displaySchedule']['lessonTimes']:
			try:
				# create a hash
				lesHash = hashlib.sha256(json.dumps(les, sort_keys=True).encode('utf-8')).hexdigest()
				if lesHash in duplicateLes:
					self._errorDialog.addData(pprint.pformat(les))
					self._errorDialog.addInfo('Found duplicate entry (hash: {:s}).'.format(lesHash))
					raise DuplicateItem()
				else:
					duplicateLes.append(lesHash)

				self._parseLesson(les)
			except DuplicateItem:
				noDuplicates += 1
			except SuperseedingItem:
				noSuperseeding += 1
			except SkippedItem:
				noSkipped += 1

		if noDuplicates > 0:
			self._errorDialog.addInfo('Skipped {:d} duplicate entries!'.format(noDuplicates))
		if noSkipped > 0:
			self._errorDialog.addInfo('Skipped {:d} entries due to not know how to interpret data!'.format(noSkipped))
		if noSuperseeding > 0:
			self._errorDialog.addInfo(
				'Skipped {:d} entries as it seems there are superseeding entries!'.format(noSuperseeding)
			)

	def findAbsentReason(self, classId, reasonRef, les):
		hashKey = '{}{}'.format(classId, reasonRef)
		try:
			classAbsentDetail = self._absentDetails[hashKey]
		except KeyError:
			pass
		else:
			for abs in classAbsentDetail:
				startDateAbsent = datetime.datetime.strptime(
					'{}{}'.format(abs['startDate'], abs['startTime']), '%Y%m%d%H%M'
				)
				endDateAbsent = datetime.datetime.strptime(
					'{}{}'.format(abs['endDate'], abs['endTime']), '%Y%m%d%H%M'
				)
				# get first date entry from standin
				chkDate = datetime.datetime.strptime(
					'{}{}'.format(les['dates'][0], les['startTime']), '%Y%m%d%H%M'
				)
				if chkDate >= startDateAbsent and chkDate <= endDateAbsent:
					if 'note' in abs:
						return abs['note']

		return None

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
				newEntry = ChangeEntry(entryDates, 4, ChangeEntry.CHANGE_TYPE_DUTY)
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

	def getResult(self, transaction=None):
		planEntries = []
		planObjects = self._absentClasses + self._absentTeacher + self._supervision + self._standin
		for f in planObjects:
			planEntries.extend(f.asDict())

		return {
			'stand': self._stand,
			'plan': planEntries,
			'ptype': self._planType,
			'class': self._classList.getList(),
			'teacher': self._teacherList.serialize(),
			'subjects': self._subjectList.serialize(),
			'timeframes': {
				'pupil': self._timeFramesPupil.serialize(),
				'duty': self._timeFramesDuty.serialize()
			},
			'hashes': {
				'pupil': hashlib.sha256(json.dumps(self._timeFramesPupil.serialize()).encode('utf-8')).hexdigest(),
				'duty': hashlib.sha256(json.dumps(self._timeFramesDuty.serialize()).encode('utf-8')).hexdigest(),
				'teacher': hashlib.sha256(json.dumps(self._teacherList.serialize()).encode('utf-8')).hexdigest(),
				'subjects': hashlib.sha256(json.dumps(self._subjectList.serialize()).encode('utf-8')).hexdigest()
			}
		}
