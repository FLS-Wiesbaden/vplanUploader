#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @author Lukas Schreiner
# @file searchplaner.py

import time, os

class SearchPlaner:
	plan = None

	def __init__(self, plan):
		self.plan = plan
		self.loopSearch()
	
	def loopSearch(self):
		while self.plan.getRun():
			time.sleep(self.plan.getIntervall())
			if self.plan.getStatus() == False:
				self.plan.getNewFiles()
