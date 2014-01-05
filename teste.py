#!/usr/bin/env python
# -*- coding: utf-8 -*-

import i18n_teste

def main():

    print "Em Português:\n"
    _ = i18n_teste.pt_language.ugettext
    print _("This is a test!\n")
    print _("This is a test!\n")
    print _(" ate")

    print "Em Inglês:\n"
    _ = i18n_teste.uk_language.ugettext
    print(_("Aleluia!\n"))
    print(_("This is a test!\n"))

if __name__=="__main__":
    main()
