#!/usr/bin/env python3
# -*- coding: utf8 -*-
#
# @author Lukas Schreiner
#

import sys
from cx_Freeze import setup, Executable

files = [
	'Microsoft.VC90.CRT.manifest',
	'msvcr90.dll',
	'msvcp90.dll',
	'msvcm90.dll',
	'config.ini',
	'fls_logo.ico'
	]

base = None
exeName = 'flsvplan'
exeDebug = 'flsvplan_debug'
if sys.platform == "win32":
	base = "Win32GUI"
	exeName = exeName + '.exe'
	exeDebug = exeDebug + '.exe'

flsvplan = Executable(
	"flsvplan.py",
	base = base,
	icon = "fls_logo.ico",
		targetName = exeName,
	copyDependentFiles = True,
	appendScriptToExe = True,
	appendScriptToLibrary = True,
	compress = True
	)

flsvplan_debug = Executable(
	"flsvplan.py",
	base = None,
	icon = "fls_logo.ico",
		targetName = exeDebug,
	copyDependentFiles = True,
	appendScriptToExe = True,
	appendScriptToLibrary = True,
	compress = False
	)

buildOpts = {
	'include_files': files,
	'copy_dependent_files': True,
	'append_script_to_exe': True
	}

setup(
	name = "FLS Vertretungsplaner",
	version = "0.5",
	description = "Vertretungsplaner Client",
	author = "Friedrich-List-Schule Wiesbaden",
	author_email = "website-team@fls-wiesbaden.de",
	url = "http://fls-wiesbaden.de",
	options = {'build_exe': buildOpts},
	executables = [flsvplan, flsvplan_debug]
)

