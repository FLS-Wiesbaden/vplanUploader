#!/usr/bin/env python3
# -*- coding: utf8 -*-
# 
# This contains the basic skeleton for creating a 
# parser.
#
# @author Lukas Schreiner

from PyQt5.QtCore import QObject, pyqtSignal

class BasicParser(QObject):

	planFileLoaded = pyqtSignal()
	planParserPrepared = pyqtSignal()
	planParsed = pyqtSignal(bool)

	def __init__(self, config, parsingFile):
		super().__init__()
		self._config = config
		self._parsingFile = parsingFile
		self._fileContent = None

	def loadFile(self, encoding=None):
		try:
			with open(self._parsingFile, 'rb') as f:
				self._fileContent = f.read()
		except Exception as e:
			if hasattr(self, _errorDialog):
				self._errorDialog.addError(
					'Could not parse the new plan with path %s because of %s' % (
						self._parsingFile, str(e)
					)
				)
			self.planParsed(False)
			return

		# now we have to guess the encoding.
		decoded = True
		if encoding is None:
			try:
				self._fileContent = self._fileContent.decode('utf-8')
			except:
				try:
					self._fileContent = self._fileContent.decode('utf-8-sig')
				except:
					try:
						self._fileContent = self._fileContent.decode('iso-8859-1')
					except:
						decoded = False
		else:
			try:
				self._fileContent = self._fileContent.decode(encoding)
			except:
				decoded = False

		if not decoded:
			if hasattr(self, _errorDialog):
				self._errorDialog.addError('Could not decode the loaded plan with path %s' % (self._parsingFile,))
			self.planParsed(False)
			return

		#self.planFileLoaded.emit()

	def preParse(self):
		self.planParserPrepared.emit()
		pass

	def parse(self):
		self.planParsed(True)
		pass

	def postParse(self):
		pass

	def getResult(self):
		pass

	def hasErrors(self):
		if hasattr(self, _errorDialog):
			return self._errorDialog.hasData
		else:
			return False

class ChangeEntry(object):

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
		self._note = ''
		self._info = ''

	def asDict(self):
		entries = []
		if len(self._course) == 0:
			self._course.append(None)

		for day in self._dates:
			for cour in self._course:
				for hour in self._hours:
					e = {
						'type': self._planType,
						'date': day,
						'hour': hour,
						'starttime': self._startTime,
						'endtime': self._endTime,
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
					entries.append(e)

		return entries