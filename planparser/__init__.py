#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Module to parse different sources of plans.

This module is there in order to parse standin plans in a standardized format.
"""

import sys

__all__ = ["basic", "fls", "davinci", "untis"]

def getParser(extension, cfg):
    for submodule in __all__:
        enabled = False
        try:
            cfgName = 'parser-{:s}'.format(submodule)
            enabled = cfg.get(cfgName, 'enabled') == 'True'
        except:
            pass
        if enabled:
            sbm = __import__(__name__ + "." + submodule, fromlist=(__name__))
            if sbm:
                # load class
                parserObj = getattr(sbm, 'Parser')
                if parserObj and extension in getattr(parserObj, 'EXTENSIONS', []):
                    return parserObj

    return None
