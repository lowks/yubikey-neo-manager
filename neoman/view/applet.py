# Copyright (c) 2013 Yubico AB
# All rights reserved.
#
#   Redistribution and use in source and binary forms, with or
#   without modification, are permitted provided that the following
#   conditions are met:
#
#    1. Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#    2. Redistributions in binary form must reproduce the above
#       copyright notice, this list of conditions and the following
#       disclaimer in the documentation and/or other materials provided
#       with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
from PySide import QtGui, QtCore
from neoman.model.applet import Applet
from neoman.model.neo import YubiKeyNeo
from neoman.storage import capstore
from neoman import messages as m
from functools import partial


class AppletPage(QtGui.QTabWidget):
    _applet = QtCore.Signal(Applet)
    _neo = QtCore.Signal(YubiKeyNeo)

    def __init__(self):
        super(AppletPage, self).__init__()

        overview = OverviewTab()
        self._applet.connect(overview.set_applet)
        self._neo.connect(overview.set_neo)
        self.addTab(overview, m.overview)

    @QtCore.Slot(Applet)
    def setApplet(self, applet):
        self._applet.emit(applet)

    @QtCore.Slot(YubiKeyNeo)
    def setNeo(self, neo):
        self._neo.emit(neo)


class OverviewTab(QtGui.QWidget):

    def __init__(self):
        super(OverviewTab, self).__init__()
        self._applet = None
        self._neo = None
        self._name = QtGui.QLabel()
        self._aid = QtGui.QLabel()
        self._status = QtGui.QLabel()

        available = QtCore.QCoreApplication.instance().available_neos
        available.changed.connect(self.data_changed)
        self._neo_selector = QtGui.QComboBox()
        self._neo_selector.activated.connect(self.neo_selected)
        for neo in available.get():
            self._neo_selector.addItem(neo.name, neo)

        top_row = QtGui.QHBoxLayout()
        top_row.addWidget(self._name)
        top_row.addWidget(self._neo_selector)

        self._install_button = QtGui.QPushButton()
        self._install_button.clicked.connect(self.install_button_click)

        status_row = QtGui.QHBoxLayout()
        status_row.addWidget(self._status)
        status_row.addWidget(self._install_button)

        layout = QtGui.QVBoxLayout()
        layout.addLayout(top_row)
        layout.addLayout(status_row)
        layout.addWidget(self._aid)
        layout.addStretch()

        self.setLayout(layout)

    def install_button_click(self):
        installed = self._neo and any(
            [x.startswith(self._applet.aid) for x in self._neo.list_apps()])
        worker = QtCore.QCoreApplication.instance().worker
        cb = lambda _: self.neo_or_applet_changed(self._neo, self._applet)
        if installed:  # Uninstall
            if QtGui.QMessageBox.Ok != QtGui.QMessageBox.warning(
                self, m.delete_app_confirm, m.delete_app_desc,
                    QtGui.QMessageBox.Ok | QtGui.QMessageBox.Cancel):
                return
            work = partial(self._neo.delete_app, self._applet.aid)
            worker.post(m.deleting_1 % self._applet.name, work, cb)
        elif self._applet.is_downloaded:  # Install
            work = partial(self._neo.install_app, self._applet.cap_file)
            worker.post(m.installing_1 % self._applet.name, work,
                        self._cb_install)
        else:  # Download
            worker.download(self._applet.cap_url, self._cb_download)

    @QtCore.Slot(object)
    def _cb_install(self, result):
        if result:
            msg = m.error_installing_1 % self._applet.name
            msg += '\n%s' % result
            QtGui.QMessageBox.warning(self, m.error_installing, msg)

        self.neo_or_applet_changed(self._neo, self._applet)

    @QtCore.Slot(object)
    def _cb_uninstall(self, result):
        if result:
            msg = m.error_uninstalling_1 % self._applet.name
            msg += '\n%s' % result
            QtGui.QMessageBox.warning(self, m.error_uninstalling, msg)

        self.neo_or_applet_changed(self._neo, self._applet)

    @QtCore.Slot(object)
    def _cb_download(self, result):
        if isinstance(result, QtCore.QByteArray):
            capstore.store_data(self._applet.aid, self._applet.latest_version,
                                result)
            self.neo_or_applet_changed(self._neo, self._applet)
        else:
            print "Error:", result

    @QtCore.Slot(Applet)
    def set_applet(self, applet):
        if applet:
            self._applet = applet
            self._name.setText(m.name_1 % applet.name)
            self._aid.setText(m.aid_1 % applet.aid)
            self.neo_or_applet_changed(self._neo, applet)

    @QtCore.Slot(YubiKeyNeo)
    def set_neo(self, neo):
        if neo and neo.has_ccid:
            self._neo = neo
            self._neo_selector.setCurrentIndex(
                self._neo_selector.findData(neo))
            self.neo_or_applet_changed(neo, self._applet)

    def neo_or_applet_changed(self, neo, applet):
        if not applet:
            return
        installed = neo and any((x.startswith(applet.aid)
                                 for x in neo.list_apps()))
        self._status.setText(m.status_1 %
                             (m.installed if installed else m.not_installed))
        btntext = m.uninstall if installed else m.install if applet.is_downloaded else m.download
        self._install_button.setText(btntext)
        self._install_button.setEnabled(bool(neo) or not applet.is_downloaded)

    @QtCore.Slot(int)
    def neo_selected(self, index):
        self.set_neo(self._neo_selector.itemData(index))

    @QtCore.Slot(list)
    def data_changed(self, new_neos):
        self._neo_selector.clear()
        new_neos = [neo for neo in new_neos if neo.has_ccid]
        for neo in new_neos:
            self._neo_selector.addItem(neo.name, neo)
        if self._neo in new_neos:
            self._neo_selector.setCurrentIndex(new_neos.index(self._neo))
        else:
            self._neo = None if not new_neos else new_neos[0]
            self.neo_or_applet_changed(self._neo, self._applet)


# class SettingsTab
# - Manage app specific settings against NEOs which have it installed.
