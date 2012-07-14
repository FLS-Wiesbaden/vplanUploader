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
if sys.platform == "win32":
    base = "Win32GUI"

flsvplan = Executable(
	"flsvplan.py",
	base = base,
	icon = "fls_logo.ico",
	targetDir = "flsvplan",
	copyDependentFiles = True,
	appendScriptToExe = True,
	appendScriptToLibrary = True,
	compress = False
	)

flsvplan_debug = Executable(
	"flsvplan.py",
	base = None,
	icon = "fls_logo.ico",
	targetDir = "flsvplan_debug",
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
	version = "0.3",
	description = "Vertretungsplaner Client DaVinci",
	author = "Friedrich-List-Schule Wiesbaden",
	author_email = "website-team@fls-wiesbaden.de",
	url = "http://fls-wiesbaden.de",
	options = {'build_exe': buildOpts},
	executables = [flsvplan, flsvplan_debug]
)

