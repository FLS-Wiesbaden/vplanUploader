#!/usr/bin/env python3
# -*- coding: utf8 -*-
#
# @author Lukas Schreiner
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QPlainTextEdit, QDialogButtonBox
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSlot
import datetime

class ErrorDialog(QDialog):

	def __init__(self, displayDebug=False, parent=None):
		super().__init__(parent)
		self.hasData = False
		self.displayDebug = displayDebug
		self.setupUi()

	@pyqtSlot(str)
	def addDebug(self, msg, data=None):
		if self.displayDebug:
			if data is not None:
				msgfmt = '<p style="color: #0035A8"><pre>%s</pre></p>'
				self.logContent.appendHtml(msgfmt % (msg,))

			self.hasData = True
			msgfmt = '<p style="color: #77B1FC">[Debug] %s: %s</p>'
			dtm = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
			self.logContent.appendHtml(msgfmt % (dtm, msg))

	@pyqtSlot(str)
	def addInfo(self, msg):
		self.hasData = True
		msgfmt = '<p style="color: #45BA02">[Info] %s: %s</p>'
		dtm = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
		self.logContent.appendHtml(msgfmt % (dtm, msg))

	@pyqtSlot(str)
	def addWarning(self, msg):
		self.hasData = True
		msgfmt = '<p style="color: #C47C00">[Warning] %s: %s</p>'
		dtm = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
		self.logContent.appendHtml(msgfmt % (dtm, msg))

	@pyqtSlot(str)
	def addError(self, msg):
		self.hasData = True
		msgfmt = '<p style="color: #D90000">[Error] %s: %s</p>'
		dtm = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
		self.logContent.appendHtml(msgfmt % (dtm, msg))

	@pyqtSlot(str)
	def addData(self, msg):
		self.hasData = True
		msgfmt = '<p style="color: #0035A8"><pre>%s</pre></p>'
		self.logContent.appendHtml(msgfmt % (msg,))

	@pyqtSlot()
	def cleanup(self):
		self.logContent.clear()

	def setupUi(self):
		self.setWindowTitle('Fehler-Log')
		self.setWindowIcon(QIcon('logo.ico'))
		self.resize(800, 800)

		# layout
		vlayout = QVBoxLayout()

		# Log Area
		self.logContent = QPlainTextEdit()
		self.logContent.setReadOnly(True)
		vlayout.addWidget(self.logContent)

		# Button Box
		buttonBox = QDialogButtonBox(QDialogButtonBox.Ok)
		buttonBox.accepted.connect(self.accept);
		vlayout.addWidget(buttonBox)

		self.setLayout(vlayout)
