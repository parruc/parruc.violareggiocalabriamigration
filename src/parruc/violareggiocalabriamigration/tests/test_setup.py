# -*- coding: utf-8 -*-
"""Setup tests for this package."""
import unittest

from parruc.violareggiocalabriamigration.testing import \
    PARRUC_VIOLAREGGIOCALABRIAMIGRATION_INTEGRATION_TESTING  # noqa
from plone import api


class TestSetup(unittest.TestCase):
    """Test that parruc.violareggiocalabriamigration is properly installed."""

    layer = PARRUC_VIOLAREGGIOCALABRIAMIGRATION_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer['portal']
        self.installer = api.portal.get_tool('portal_quickinstaller')

    def test_product_installed(self):
        """Test if parruc.violareggiocalabriamigration is installed."""
        self.assertTrue(self.installer.isProductInstalled(
            'parruc.violareggiocalabriamigration'))

    def test_browserlayer(self):
        """Test that IParrucViolareggiocalabriamigrationLayer is registered."""
        from parruc.violareggiocalabriamigration.interfaces import (
            IParrucViolareggiocalabriamigrationLayer)
        from plone.browserlayer import utils
        self.assertIn(IParrucViolareggiocalabriamigrationLayer,
                      utils.registered_layers())


class TestUninstall(unittest.TestCase):

    layer = PARRUC_VIOLAREGGIOCALABRIAMIGRATION_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.installer = api.portal.get_tool('portal_quickinstaller')
        self.installer.uninstallProducts(
            ['parruc.violareggiocalabriamigration'])

    def test_product_uninstalled(self):
        """Test if parruc.violareggiocalabriamigration
           is cleanly uninstalled."""
        self.assertFalse(self.installer.isProductInstalled(
            'parruc.violareggiocalabriamigration'))

    def test_browserlayer_removed(self):
        """Test that IParrucViolareggiocalabriamigrationLayer is removed."""
        from parruc.violareggiocalabriamigration.interfaces import\
            IParrucViolareggiocalabriamigrationLayer
        from plone.browserlayer import utils
        self.assertNotIn(IParrucViolareggiocalabriamigrationLayer,
                         utils.registered_layers())
