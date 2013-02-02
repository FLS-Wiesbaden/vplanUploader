# -*- coding: utf-8 -*-
import sys
from PyQt4 import QtGui
from PyQt4.QtCore import pyqtSlot

class Taskbar(QtGui.QSystemTrayIcon):

	def __init__(self, par, icon, title, menu):
		QtGui.QSystemTrayIcon.__init__(self, icon, par)
		self.menu = QtGui.QMenu(par)
		for i in menu:
			action = QtGui.QAction(i[0], None)
			action.setData(i[2])
			action.triggered.connect(self.menuItemCalled)
			act = self.menu.addAction(action)
		self.setContextMenu(self.menu)

	@pyqtSlot(bool)
	def menuItemCalled(self, state):
		method = self.sender().data()
		method()

	def showInfo(self, title, msg):
		self.showMessage(title, msg)