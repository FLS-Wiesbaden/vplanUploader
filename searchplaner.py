#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @author Lukas Schreiner
# @file searchplaner.py

import time, os

class SearchPlaner():
	plan = None
	
	def loopSearch(self):
		while self.plan.getRun():
			time.sleep(self.plan.getIntervall()) #300 - 5 Minuten
			if self.plan.getStatus() == False:
				self.plan.getNewFiles()

	def __init__(self, plan):
		self.plan = plan

		self.loopSearch()
