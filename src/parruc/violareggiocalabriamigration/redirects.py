# -*- coding: utf-8 -*-
import logging

from zope.component import getUtility
from zope.interface import classProvides, implements

from collective.transmogrifier.interfaces import ISection, ISectionBlueprint
from collective.transmogrifier.utils import Condition

try:
    from plone.app.redirector.interfaces import IRedirectionStorage
    redirect = True
except:
    redirect = False

logger = logging.getLogger('plone.app.transmogrifier.object_implementer')


class RedirectsSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context
        self.sourcekey = options.get('source-key', '_redirect_source')
        self.destkey = options.get('dest-key', '_redirect_dest')
        self.condition = Condition(options.get('condition', 'python:True'),
                                   transmogrifier, name, options)
        self.storage = getUtility(IRedirectionStorage)

    def __iter__(self):

        for item in self.previous:
            if not self.condition(item):
                yield item
            if self.destkey not in item or self.sourcekey not in item:
                yield item
                continue
            source = item[self.sourcekey]
            dest = item[self.destkey]
            logger.warning("adding redirect %s to %s", source, dest)
            self.storage.add(source, dest)
            yield item
