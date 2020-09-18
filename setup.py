#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# @author Lukas Schreiner
#

import sys
import os.path
import subprocess
import shlex
import glob
import zipfile
import shutil
from cx_Freeze import setup, Executable
scriptDir = os.path.dirname(os.path.realpath(__file__))
buildDir = os.path.join(scriptDir, 'build')
distDir = os.path.join(scriptDir, 'dist')

def addToZip(zipFile, p):
	if os.path.isdir(p):
		for fls in glob.glob(os.path.join(p, '*'), recursive=True):
			addToZip(zipFile, fls)
	else:
		zipFile.write(p, os.path.relpath(p, buildDir))

files = [
	os.path.join(scriptDir, 'config.ini.sample'),
]
if os.path.exists(os.path.join(scriptDir, 'config.ini')):
	files.append(os.path.join(scriptDir, 'config.ini'))

# really dirty hack for Windows Server
if sys.platform == 'win32':
	# Platforms plugins
	pluginPath = os.path.join(
		os.path.dirname(sys.executable),
		'..\\Lib\\site-packages\\PyQt5\\Qt\\plugins\\platforms'
	)
	for f in glob.glob(pluginPath + '\\*.dll'):
		files.append((f, 'platforms\\' + os.path.basename(f)))
	# Image formats plugins
	pluginPath = os.path.join(
		os.path.dirname(sys.executable),
		'..\\Lib\\site-packages\\PyQt5\\Qt\\plugins\\imageformats'
	)
	for f in glob.glob(pluginPath + '\\*.dll'):
		files.append((f, 'imageformats\\' + os.path.basename(f)))

# DEFAULT VALUES
setupVersion = "4.29"
setupDescription = "Vertretungsplaner Client"
setupPublisher = 'Friedrich-List-Schule Wiesbaden'
setupPublisherMail = 'website-team@fls-wiesbaden.de'

if sys.argv[-1] in ['gks', 'fls', 'sds']:
	variant = sys.argv.pop()
else:
	variant = 'fls'

setupSrcIco = '%s.ico' % (variant,)
if variant == 'fls':
	setupName = 'FLS Vertretungsplaner'
	setupUrl = 'https://www.fls-wiesbaden.de'
	setupGuid = 'ED537E23-D959-4C1A-AEBD-580CDF68E450'
elif variant == 'gks':
	setupUrl = 'https://vplan.gks-obertshausen.de'
	setupName = 'GKS Vertretungsplaner'
	setupGuid = '22A5D5F7-0677-4691-9D08-5CE05E11AAFD'
elif variant == 'sds':
	setupUrl = 'https://sds.fls-wiesbaden.de'
	setupName = 'SDS Vertretungsplaner'
	setupGuid = '7CE997E4-8D0A-4406-A3EA-F48CAB29F4A9'
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
	'zip_include_packages': ['PyQt5.QtNetwork', 'PyQt5.sip', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 'PyQt5', 'sip'],
	'include_msvcr': True,
	'includes': ['queue'],
	'build_exe': os.path.join(buildDir, 'vplan-{:s}'.format(setupVersion))
}

setup(
	name = setupName,
	version = setupVersion,
	description = setupDescription,
	author = setupPublisher,
	author_email = setupPublisherMail,
	url = setupUrl,
	options = {'build_exe': buildOpts},
	executables = [flsvplan, flsvplan_debug]
)

# inno setup?
if sys.platform == "win32":
	cmd = 'iscc \
	/DMyAppVersion="{version}" \
	/DMyAppName="{name}" \
	/DMyAppPublisher="{publisher}" \
	/DMyAppURL="{url}" \
	/DMyAppExeName="{exeName}" \
	/DbuildDirectory="{buildDirectory}" \
	/DMyAppGuid="{appGuid}" \
	inno_setup.iss'.format(
		version=setupVersion,
		name=setupName,
		publisher=setupPublisher,
		url=setupUrl,
		exeName=exeName,
		buildDirectory=os.path.join(buildDir, 'vplan-{:s}'.format(setupVersion)),
		appGuid=setupGuid
	)
	exeCmd = shlex.split(cmd)
	p = subprocess.Popen(exeCmd)
	p.communicate()
	# copy setup file to build directory.
	srcSetupFile = os.path.join(scriptDir, 'Output', setupName + '_' + setupVersion + '_setup.exe')
	dstSetupFile = os.path.join(buildDir, setupName + '_' + setupVersion + '_setup.exe')
	if os.path.exists(srcSetupFile):
		shutil.copyfile(srcSetupFile, dstSetupFile)

# create dist file.
if not os.path.exists(distDir):
	try:
		os.makedirs(distDir, exist_ok=True)
	except:
		pass

distZipName = os.path.join(distDir, 'vplan-{:s}.zip'.format(setupVersion))
zf = zipfile.ZipFile(distZipName, 'w', compression=zipfile.ZIP_DEFLATED)
for fls in glob.glob(os.path.join(buildDir, 'vplan-{:s}'.format(setupVersion), '*'), recursive=True):
	addToZip(zf, fls)

zf.close()
