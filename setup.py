#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# @author Lukas Schreiner
#

import sys, os.path
from cx_Freeze import setup, Executable
scriptDir = os.path.dirname(os.path.realpath(__file__))

files = [
	os.path.join(scriptDir, 'config.ini.sample'),
]
if os.path.exists(os.path.join(scriptDir, 'config.ini')):
	files.append(os.path.join(scriptDir, 'config.ini'))

# DEFAULT VALUES
setupName = 'FLS Vertretungsplaner'
setupVersion = "4.25"
setupDescription = "Vertretungsplaner Client"
setupUrl = 'https://www.fls-wiesbaden.de'
setupPublisher = 'Friedrich-List-Schule Wiesbaden'
setupPublisherMail = 'website-team@fls-wiesbaden.de'
setupSrcIco = 'fls.ico'
if sys.argv[-1] in ['gks', 'fls']:
	variant = sys.argv.pop()
	setupSrcIco = '%s.ico' % (variant,)
	if variant == 'gks':
		setupUrl = 'https://vplan.gks-obertshausen.de'
		setupName = 'GKS Vertretungsplaner'
setupIco = os.path.join(scriptDir, 'pixmaps', setupSrcIco)
files.append((setupIco, 'logo.ico'))

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
	copyright = setupPublisher
)

flsvplan_debug = Executable(
	"flsvplan.py",
	base = None,
	icon = setupIco,
	targetName = exeDebug,
	copyright = setupPublisher
)

buildOpts = {
	'include_files': files,
	'zip_include_packages': ['PyQt5'],
	'include_msvcr': True,
	'build_exe': os.path.join('build', 'vplan-{:s}'.format(setupVersion))
}

setup(
	name = setupName,
	version = setupVersion,
	description = setupDescription,
	author = setupPublisher,
	author_email = setupPublisherMail
	url = setupUrl,
	options = {'build_exe': buildOpts},
	executables = [flsvplan, flsvplan_debug]
)
