# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2015 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""The nil plugin is useful for parts with no source.

Using this, parts can be defined purely by utilizing properties automatically
included by Snapcraft, e.g. stage-packages.
"""

from snapcraft_legacy.plugins.v1 import PluginV1


class NilPlugin(PluginV1):
    def enable_cross_compilation(self):
        pass
