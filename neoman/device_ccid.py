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
from neoman.ykneomgr import *
from ctypes import POINTER, byref, c_size_t, create_string_buffer
from neoman.device import BaseDevice
import os


if ykneomgr_global_init(1 if os.environ.has_key('NEOMAN_DEBUG') else 0) != 0:
    raise Exception("Unable to initialize ykneomgr")


def check(status):
    if status != 0:
        raise Exception("Error: %d" % status)


class CCIDDevice(BaseDevice):

    def __init__(self, dev, dev_str=None):
        self._dev = dev
        self._dev_str = dev_str
        self._key = None
        self._locked = True
        self._serial = ykneomgr_get_serialno(dev) or None
        self._mode = ykneomgr_get_mode(dev)
        self._version = [
            ykneomgr_get_version_major(dev),
            ykneomgr_get_version_minor(dev),
            ykneomgr_get_version_build(dev)
        ]

    @property
    def key(self):
        return self._key

    @key.setter
    def key(self, new_key):
        self._key = new_key

    @property
    def locked(self):
        return self._locked

    @property
    def mode(self):
        return self._mode

    @property
    def serial(self):
        return self._serial

    @property
    def version(self):
        return self._version

    def unlock(self):
        self._locked = True
        if not self._key:
            raise Exception("No transport key provided!")
        check(ykneomgr_authenticate(self._dev, self._key))
        self._locked = False

    def set_mode(self, mode):
        check(ykneomgr_modeswitch(self._dev, mode))
        self._mode = mode

    def list_apps(self):
        if self.locked:
            self.unlock()
        size = c_size_t()
        ykneomgr_applet_list(self._dev, None, byref(size))
        applist = create_string_buffer(size.value)
        ykneomgr_applet_list(self._dev, applist, byref(size))
        apps = applist.raw.strip('\0').split('\0')

        return apps

    def delete_app(self, aid):
        if self.locked:
            self.unlock()
        aid_bytes = aid.decode('hex')
        check(ykneomgr_applet_delete(self._dev, aid_bytes, len(aid_bytes)))

    def install_app(self, path):
        if self.locked:
            self.unlock()
        check(ykneomgr_applet_install(self._dev, create_string_buffer(path)))

    def close(self):
        if hasattr(self, '_dev'):
            ykneomgr_done(self._dev)
            del self._dev


def open_first_device():
    dev = POINTER(ykneomgr_dev)()
    check(ykneomgr_init(byref(dev)))
    try:
        check(ykneomgr_discover(dev))
    except Exception:
        ykneomgr_done(dev)
        raise

    return CCIDDevice(dev)


def open_all_devices(existing=None):
    dev = POINTER(ykneomgr_dev)()
    check(ykneomgr_init(byref(dev)))
    size = c_size_t()
    check(ykneomgr_list_devices(dev, None, byref(size)))
    devlist = create_string_buffer(size.value)
    check(ykneomgr_list_devices(dev, devlist, byref(size)))
    names = devlist.raw.strip('\0').split('\0')
    devices = []
    for d in existing or []:
        if getattr(d, '_dev_str', None) in names:
            devices.append(d)
            names.remove(d._dev_str)
    for name in names:
        if not dev:
            dev = POINTER(ykneomgr_dev)()
            check(ykneomgr_init(byref(dev)))
        if ykneomgr_connect(dev, create_string_buffer(name)) == 0:
            devices.append(CCIDDevice(dev, name))
            dev = None
    return devices
