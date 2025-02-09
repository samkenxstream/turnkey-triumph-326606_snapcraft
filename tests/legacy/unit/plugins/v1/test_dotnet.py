# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2017-2018-2020 Canonical Ltd
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

import json
import os
import tarfile
from unittest import mock

from testtools.matchers import Contains, DirExists, Equals, FileExists, Not

import snapcraft_legacy
from snapcraft_legacy import file_utils
from snapcraft_legacy.internal import sources
from snapcraft_legacy.plugins.v1 import dotnet
from tests.legacy import unit

from . import PluginsV1BaseTestCase


def _setup_dirs(plugin):
    os.makedirs(plugin.builddir)
    open(os.path.join(plugin.builddir, "test-app.xxproj"), "w").close()
    os.makedirs(plugin.installdir)
    executable_path = os.path.join(plugin.installdir, "test-app")
    open(executable_path, "w").close()


class DotNetPluginPropertiesTest(unit.TestCase):
    def test_schema(self):
        schema = dotnet.DotNetPlugin.schema()
        self.assertThat(schema, Contains("required"))

    def test_get_pull_properties(self):
        expected_pull_properties = ["dotnet-runtime-version", "dotnet-version"]
        self.assertThat(
            dotnet.DotNetPlugin.get_pull_properties(), Equals(expected_pull_properties)
        )

    def test_get_build_properties(self):
        expected_build_properties = []
        self.assertThat(
            dotnet.DotNetPlugin.get_build_properties(),
            Equals(expected_build_properties),
        )


class DotNetProjectBaseTest(PluginsV1BaseTestCase):
    def setUp(self):
        super().setUp()

        class Options:
            build_attributes = []
            dotnet_runtime_version = dotnet._RUNTIME_DEFAULT
            dotnet_version = dotnet._VERSION_DEFAULT

        self.options = Options()

        # Only amd64 is supported for now.
        patcher = mock.patch(
            "snapcraft_legacy.ProjectOptions.deb_arch",
            new_callable=mock.PropertyMock,
            return_value="amd64",
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        def fake_urlopen(request):
            return FakeResponse(request.full_url, checksum)

        class FakeResponse:
            def __init__(self, url: str, checksum: str) -> None:
                self._url = url
                self._checksum = checksum

            def read(self):
                return json.dumps(
                    {
                        "releases": [
                            {
                                "release-version": "2.0.9",
                                "sdk": {
                                    "runtime-version": "2.0.9",
                                    "files": [
                                        {
                                            "name": "dotnet-sdk-linux-x64.tar.gz",
                                            "rid": "linux-x64",
                                            "url": "https://download.microsoft.com/download/f/c/1/fc16c864-b374-4668-83a2-f9f880928b2d/dotnet-sdk-2.1.202-linux-x64.tar.gz",
                                            "hash": "c1b07ce8849619ca505aafd2983bcdd7141536ccae243d4249b0c9665daf107e03a696ad5f1d95560142cd841a0888bbf5f1a8ff77d3bdc3696b5873481f0998",
                                        }
                                    ],
                                },
                            }
                        ]
                    }
                ).encode("utf-8")

        with tarfile.open("test-sdk.tar", "w") as test_sdk_tar:
            open("test-sdk", "w").close()
            test_sdk_tar.add("test-sdk")
        checksum = file_utils.calculate_hash("test-sdk.tar", algorithm="sha512")

        patcher = mock.patch("urllib.request.urlopen")
        urlopen_mock = patcher.start()
        urlopen_mock.side_effect = fake_urlopen
        self.addCleanup(patcher.stop)

        original_check_call = snapcraft_legacy.internal.common.run
        patcher = mock.patch("snapcraft_legacy.internal.common.run")
        self.mock_check_call = patcher.start()
        self.addCleanup(patcher.stop)

        def side_effect(cmd, *args, **kwargs):
            if cmd[0].endswith("dotnet"):
                pass
            else:
                original_check_call(cmd, *args, **kwargs)

        self.mock_check_call.side_effect = side_effect


class TestDotNetErrors:

    scenarios = (
        (
            "DotNetBadArchitectureError",
            {
                "exception_class": dotnet.DotNetBadArchitectureError,
                "kwargs": {"architecture": "wrong-arch", "supported": ["arch"]},
                "expected_message": (
                    "Failed to prepare the .NET SDK: "
                    "The architecture 'wrong-arch' is not supported. "
                    "Supported architectures are: 'arch'."
                ),
            },
        ),
        (
            "DotNetBadReleaseDataError",
            {
                "exception_class": dotnet.DotNetBadReleaseDataError,
                "kwargs": {"version": "test"},
                "expected_message": (
                    "Failed to prepare the .NET SDK: "
                    "An error occurred while fetching the version details "
                    "for 'test'. Check that the version is correct."
                ),
            },
        ),
    )

    def test_error_formatting(self, exception_class, kwargs, expected_message):
        assert str(exception_class(**kwargs)) == expected_message


class DotNetProjectTest(DotNetProjectBaseTest):
    def test_sdk_in_path(self):
        plugin = dotnet.DotNetPlugin("test-part", self.options, self.project)
        self.assertThat(
            plugin.env(plugin.installdir),
            Contains("PATH={}:$PATH".format(plugin._dotnet_sdk_dir)),
        )
        # Be sure that the PATH doesn't leak into the final snap
        self.assertThat(plugin.env(self.project.stage_dir), Equals([]))
        self.assertThat(plugin.env(self.project.prime_dir), Equals([]))

    def test_init_with_non_amd64_architecture(self):
        with mock.patch(
            "snapcraft_legacy.ProjectOptions.deb_arch",
            new_callable=mock.PropertyMock,
            return_value="non-amd64",
        ):
            error = self.assertRaises(
                dotnet.DotNetBadArchitectureError,
                dotnet.DotNetPlugin,
                "test-part",
                self.options,
                self.project,
            )
        self.assertThat(error.architecture, Equals("non-amd64"))

    def test_pull_sdk(self):
        plugin = dotnet.DotNetPlugin("test-part", self.options, self.project)
        with mock.patch.object(sources.Tar, "download", return_value="test-sdk.tar"):
            plugin.pull()

        self.assertThat(
            os.path.join("parts", "test-part", "dotnet", "sdk", "test-sdk"),
            FileExists(),
        )

    def test_clean_pull_removes_dotnet_dir(self):
        dotnet_dir = os.path.join("parts", "test-part", "dotnet", "sdk")
        os.makedirs(dotnet_dir)
        plugin = dotnet.DotNetPlugin("test-part", self.options, self.project)
        plugin.clean_pull()
        self.assertThat(dotnet_dir, Not(DirExists()))

    def test_build_changes_executable_permissions(self):
        plugin = dotnet.DotNetPlugin("test-part", self.options, self.project)
        _setup_dirs(plugin)
        plugin.build()

        self.assertThat(
            os.stat(os.path.join(plugin.installdir, "test-app")).st_mode & 0o777,
            Equals(0o755),
        )


class DotNetProjectBuildCommandsTest(DotNetProjectBaseTest):
    def run_test(self, configuration, build_attributes):
        self.options.build_attributes = build_attributes
        plugin = dotnet.DotNetPlugin("test-part", self.options, self.project)
        _setup_dirs(plugin)
        plugin.build()

        part_dir = os.path.join(self.path, "parts", "test-part")
        dotnet_command = os.path.join(part_dir, "dotnet", "sdk", "dotnet")
        self.assertThat(
            self.mock_check_call.mock_calls,
            Equals(
                [
                    mock.call(
                        [dotnet_command, "build", "-c", configuration], cwd=mock.ANY
                    ),
                    mock.call(
                        [
                            dotnet_command,
                            "publish",
                            "-c",
                            configuration,
                            "-o",
                            plugin.installdir,
                            "--self-contained",
                            "-r",
                            "linux-x64",
                        ],
                        cwd=mock.ANY,
                    ),
                ]
            ),
        )

    def test_debug(self):
        self.run_test("Debug", ["debug"])

    def test_release(self):
        self.run_test("Release", ["release"])
