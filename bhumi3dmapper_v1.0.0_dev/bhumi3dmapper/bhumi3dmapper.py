# -*- coding: utf-8 -*-
"""Main plugin class — registers menu, toolbar, and Processing provider."""
import os
import traceback

from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import Qt, QCoreApplication
from qgis.core import QgsApplication, Qgis


def tr(msg):
    return QCoreApplication.translate('Bhumi3DMapper', msg)


class Bhumi3DMapper:
    """QGIS Plugin — Bhumi3DMapper."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = tr('Bhumi3DMapper')
        self.toolbar = None
        self.dock = None
        self.provider = None

    # ── Lifecycle ─────────────────────────────────────────────────────────
    def initGui(self):
        """Create menu entries and toolbar icons."""
        try:
            self._register_provider()
            self._add_action(
                icon_name='icon.png',
                text=tr('Open Project Panel'),
                callback=self.openPanel,
                tooltip=tr('Open the Bhumi3DMapper prospectivity panel'),
                add_to_toolbar=True,
            )
            self._add_action(
                icon_name='icon.png',
                text=tr('Quick Start Wizard'),
                callback=self.openWizard,
                tooltip=tr('Step-by-step wizard — fastest way to get your first map'),
                add_to_toolbar=False,
            )
        except Exception:  # pragma: no cover
            self.iface.messageBar().pushMessage(
                'Bhumi3DMapper',
                tr('Failed to initialise plugin. See QGIS log for details.'),
                level=Qgis.Critical, duration=10)
            QgsApplication.instance().messageLog().logMessage(
                traceback.format_exc(), 'Bhumi3DMapper', Qgis.Critical)

    def unload(self):
        """Remove all plugin UI elements."""
        if self.provider:
            QgsApplication.processingRegistry().removeProvider(self.provider)
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
        if self.dock:
            self.iface.removeDockWidget(self.dock)
            self.dock = None
        if self.toolbar:
            del self.toolbar

    # ── Actions ────────────────────────────────────────────────────────────
    def openPanel(self):
        """Open (or show) the dockable project panel."""
        try:
            if self.dock is None:
                from .ui.dock_panel import BhumiDockWidget
                self.dock = BhumiDockWidget(self.iface)
                self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
            self.dock.show()
            self.dock.raise_()
        except Exception:
            self._show_error(tr('Could not open the project panel.'))

    def openWizard(self):
        """Open the Quick Start Wizard."""
        try:
            from .ui.wizard import BhumiWizard
            wizard = BhumiWizard(self.iface.mainWindow())
            wizard.exec_()
        except Exception:
            self._show_error(tr('Could not open the wizard.'))

    # ── Private helpers ────────────────────────────────────────────────────
    def _register_provider(self):
        from .provider import Bhumi3DProvider
        self.provider = Bhumi3DProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def _add_action(self, icon_name, text, callback, tooltip='',
                    add_to_toolbar=True):
        icon = QIcon(os.path.join(self.plugin_dir, icon_name))
        action = QAction(icon, text, self.iface.mainWindow())
        action.triggered.connect(callback)
        action.setToolTip(tooltip)
        self.iface.addPluginToMenu(self.menu, action)
        if add_to_toolbar:
            self.iface.addToolBarIcon(action)
        self.actions.append(action)
        return action

    def _show_error(self, msg):
        QgsApplication.instance().messageLog().logMessage(
            traceback.format_exc(), 'Bhumi3DMapper', Qgis.Critical)
        QMessageBox.critical(self.iface.mainWindow(), 'Bhumi3DMapper', msg)
