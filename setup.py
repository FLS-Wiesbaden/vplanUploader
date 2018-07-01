#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# @author Lukas Schreiner
#

import sys, os.path
from cx_Freeze import setup, Executable
scriptDir = os.path.dirname(os.path.realpath(__file__))

files = [
	# 'Microsoft.VC90.CRT.manifest',
	## Include automatically if available?
	#'msvcr90.dll',
	#'msvcp90.dll',
	#'msvcm90.dll',
	os.path.join(scriptDir, 'config.ini.sample')
]
if os.path.exists(os.path.join(scriptDir, 'config.ini')):
	files.append(os.path.join(scriptDir, 'config.ini'))

# DEFAULT VALUES
setupName = 'FLS Vertretungsplaner'
setupVersion = "4.25"
setupDescription = "Vertretungsplaner Client"
setupUrl = 'https://www.fls-wiesbaden.de'
setupIco = 'fls.ico'
if sys.argv[-1] in ['gks', 'fls']:
	variant = sys.argv.pop()
	setupIco = '%s.ico' % (variant,)
	files.append(os.path.join(scriptDir, 'pixmaps', setupIco))
	if variant == 'gks':
		setupUrl = 'http://vplan.gks-obertshausen.de'
		setupName = 'GKS Vertretungsplaner'
files.append((os.path.join(scriptDir, 'pixmaps', setupIco), 'logo.ico'))

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
	icon = setupIco,
	targetName = exeName,
	#copyDependentFiles = True,
	#appendScriptToExe = True,
	#appendScriptToLibrary = True,
)

flsvplan_debug = Executable(
	"flsvplan.py",
	base = None,
	icon = setupIco,
	targetName = exeDebug,
	#copyDependentFiles = True,
	#appendScriptToExe = True,
	#appendScriptToLibrary = True,
)

buildOpts = {
	'include_files': files,
	#'copy_dependent_files': True,
	#'append_script_to_exe': True,
}

setup(
	name = setupName,
	version = setupVersion,
	description = setupDescription,
	author = "Friedrich-List-Schule Wiesbaden",
	author_email = "website-team@fls-wiesbaden.de",
	url = setupUrl,
	options = {'build_exe': buildOpts},
	executables = [flsvplan, flsvplan_debug]
)
