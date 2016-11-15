#!/usr/bin/env python3
# -*- coding: utf8 -*-
# 
# This contains the basic skeleton for creating a 
# parser.
#
# @author Lukas Schreiner
import time
import csv
from parser.basic import BasicParser, ChangeEntry

class FlsCsvParser(BasicParser):

	def __init__(self, config, errorDialog, parsingFile):
		super().__init__(config, parsingFile)
		self._errorDialog = errorDialog
		self._classList = []
		self._plan = []
		self._stand = None
		self._planRows = []

	def loadFile(self):
		self._fileContent = []
		f = open(self._parsingFile, 'r', encoding='utf-8' if self.config.getboolean('default', 'utf8') else 'iso-8859-1')
		reader = csv.reader(f, delimiter=';')
		for row in reader:
			self._fileContent.append(row)
		f.close()

	def preParse(self):
		self._stand = int(time.time())
		self.planParserPrepared.emit()

	def parse(self):
		planParsedSuccessful = True
		try:
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

			newEntry = ChangeEntry([entryDate], 3, None)
			hours = list(range(hours[0], hours[1] + 1))
			newEntry._hours = hours
			newEntry._teacher = teacher
			newEntry._subject = subject
			newEntry._course = className.strip()
			newEntry._info = info
			newEntry._note = note
			self._plan.append(newEntry)

		except Exception as e:
			self._errorDialog.addError('Could not parse the plan. Unexpected error occured: %s.' % (str(e),))
			planParsedSuccessful = False
			raise
		finally:
			self.planParsed.emit(planParsedSuccessful)

	def getResult(self):
		planEntries = []
		for f in self._plan:
			planEntries.extend(f.asDict())

		return {
			'stand': self._stand,
			'plan': planEntries,
			'class': self._classList.getList()
		}