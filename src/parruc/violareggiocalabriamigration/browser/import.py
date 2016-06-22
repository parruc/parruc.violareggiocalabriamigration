# -*- coding: utf-8 -*-
from zope.interface import alsoProvides

from collective.transmogrifier.transmogrifier import Transmogrifier
from plone.protect.interfaces import IDisableCSRFProtection
from Products.Five.browser import BrowserView


class ImportViolaReggiocalabria(BrowserView):
    pipeline = u'parruc.violareggiocalabriamigration.import'

    def __call__(self):
        alsoProvides(self.request, IDisableCSRFProtection)
        if not self.pipeline:
            return 'nessuna pipeline definita'
        transmogrifier = Transmogrifier(self.context)
        transmogrifier(self.pipeline)
        res = ['Migrazione effettuata']

        return '\n'.join(res)
