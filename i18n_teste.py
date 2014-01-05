#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys
import locale
import gettext

# Change this variable to your app name!
#  The translation files will be under
#  @LOCALE_DIR@/@LANGUAGE@/LC_MESSAGES/@APP_NAME@.mo
APP_NAME = "teste"
#APP_DIR = os.path.join (sys.prefix, 'share')
APP_DIR=""
LOCALE_DIR = os.path.join(APP_DIR, 'i18n') # .mo files will then be located in APP_Dir/i18n/LANGUAGECODE/LC_MESSAGES/
DEFAULT_LANGUAGES = os.environ.get('LANG', '').split(':')
DEFAULT_LANGUAGES += ['en_US']

lc, encoding = locale.getdefaultlocale()
if lc:
    languages = [lc]
else:
    languages = []
    
# Concat all languages (env + default locale),
#  and here we have the languages and location of the translations
languages += DEFAULT_LANGUAGES
mo_location = LOCALE_DIR

gettext.install(True, localedir=None, unicode=1)
gettext.find(APP_NAME, mo_location)
gettext.textdomain(APP_NAME)
gettext.bind_textdomain_codeset(APP_NAME, "UTF-8")
pt_language = gettext.translation(APP_NAME, mo_location, languages=["pt_PT"], fallback=True)
uk_language = gettext.translation(APP_NAME, mo_location, languages=["en_US"], fallback=True)