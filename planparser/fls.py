#!/usr/bin/env python3
# -*- coding: utf8 -*-
# 
# This contains the basic skeleton for creating a 
# parser.
#
# @author Lukas Schreiner
import hashlib
import json
import time
import csv
from planparser import basic
from planparser.basic import ChangeEntry

class Parser(basic.Parser):

	EXTENSIONS = ['.csv']

	def __init__(self, config, errorDialog, parsingFile):
		super().__init__(config, errorDialog, parsingFile)
		self._classList = basic.SchoolClassList()
		self._plan = []
		self._planRows = []
		self._planType |= basic.Parser.PLAN_ADDITIONAL

	@staticmethod
	def isResponsible(extension):
		return extension in ['.csv']

	def loadFile(self, transaction=None):
		if self._config.has_option('parser-fls', 'encoding'):
			self._encoding = self._config.get('parser-fls', 'encoding')
		elif self._encoding is None:
			self._encoding = 'utf-8'

		self._fileContent = []
		f = open(self._parsingFile, 'r', encoding=self._encoding)
		reader = csv.reader(f, delimiter=';')
		for row in reader:
			self._fileContent.append(row)
		f.close()

	def preParse(self, transaction=None):
		self._stand = int(time.time())
		self.planParserPrepared.emit()

	def parse(self, transaction=None):
		planParsedSuccessful = True
		try:
			for row in self._fileContent:
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

				newEntry = ChangeEntry([entryDate], basic.Parser.PLAN_ADDITIONAL, ChangeEntry.CHANGE_TYPE_ADD_INFO)
				tHours = []
				for h in list(range(hours[0], hours[1] + 1)):
					tHours.append(basic.TimeFrame(hour=h))
				className = className.strip()
				newEntry._hours = tHours
				newEntry._teacher = teacher
				newEntry._subject = subject
				newEntry._room = room
				newEntry._course = [className]
				newEntry._info = info
				newEntry._note = note
				self._plan.append(newEntry)
				if className:
					try:
						classObj = self._classList[className]
					except KeyError:
						self._classList.append(basic.SchoolClass(className))
		except Exception as e:
			self._errorDialog.addError('Could not parse the plan. Unexpected error occured: %s.' % (str(e),))
			planParsedSuccessful = False
			raise
		finally:
			self.planParsed.emit(planParsedSuccessful)

	def getResult(self, transaction=None):
		planEntries = []
		for f in self._plan:
			planEntries.extend(f.asDict())

		encClasses = self._classList.serialize()
		return {
			'stand': self._stand,
			'plan': planEntries,
			'ptype': self._planType,
			'class': encClasses,
			'hashes': {
				'classes': hashlib.sha256(json.dumps(encClasses).encode('utf-8')).hexdigest()
			}
		}
