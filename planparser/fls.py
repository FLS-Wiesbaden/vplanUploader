#!/usr/bin/env python3
# -*- coding: utf8 -*-
# 
# This contains the basic skeleton for creating a 
# parser.
#
# @author Lukas Schreiner
import time
import csv
from planparser.basic import BasicParser, ChangeEntry

class FlsCsvParser(BasicParser):

	def __init__(self, config, errorDialog, parsingFile):
		super().__init__(config, parsingFile)
		self._errorDialog = errorDialog
		self._classList = []
		self._plan = []
		self._stand = None
		self._planRows = []
		self._planType = self._planType | BasicParser.PLAN_ADDITIONAL

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

				newEntry = ChangeEntry([entryDate], 16, None)
				tHours = []
				for h in list(range(hours[0], hours[1] + 1)):
					tHours.append({'hour': h, 'start': None, 'end': None})
				newEntry._hours = tHours
				newEntry._teacher = teacher
				newEntry._subject = subject
				newEntry._room = room
				newEntry._course = [className.strip()]
				newEntry._info = info
				newEntry._note = note
				self._plan.append(newEntry)
				if len(className.strip()) > 0 and className.strip() not in self._classList:
					self._classList.append(className.strip())
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

		return {
			'stand': self._stand,
			'plan': planEntries,
			'ptype': self._planType,
			'class': self._classList
		}
