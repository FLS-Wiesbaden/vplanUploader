from distutils.core import setup
import py2exe

class Target:
    def __init__(self, **kw):
        self.__dict__.update(kw)
        self.version = "0.1.1"
        self.company_name = "Friedrich-List-Schule Wiesbaden"
        self.copyright = "Website-Team FLS Wiesbaden"
        self.name = "FLS Vertretungsplaner"
        self.author = "Lukas Schreiner"
        self.author_email = "lukas.schreiner@fls-wiesbaden.de"
        self.url = "http://fls-wiesbaden.de"


flsvplan = Target(
    description = "Vertretungsplaner Friedrich-List-Schule Wiesbaden",
    script = "flsvplan.py",
    icon_resources = [(1, "fls_logo.ico")],
    dest_base = "flsvplan")

flsvplan_debug = Target(
    description = "Vertretungsplaner Friedrich-List-Schule Wiesbaden - DEBUG",
    script = "flsvplan.py",
    icon_resources = [(1, "fls_logo.ico")],
    dest_base = "flsvplan_debug")

opts = {
    "py2exe":{
        "includes":["win32gui","win32con","win32api"],
        "bundle_files": 1
        }
    }

files = [
    ('Microsoft.VC90.CRT', ["Microsoft.VC90.CRT.manifest", "msvcr90.dll", "msvcp90.dll", "msvcm90.dll"]),
    ('.', ["config.ini", "fls_logo.ico"])
    ]

setup(
    windows = [flsvplan],
    console = [flsvplan_debug],
    options = opts,
    data_files = files,
    zipfile = None,
    )

