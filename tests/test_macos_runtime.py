# SPDX-License-Identifier: LGPL-3.0-or-later
"""Platform regressions runnable without a FreeCAD GUI.

The pure macOS helper is imported normally. CfdTools' platform functions are
compiled directly from its source AST so their actual bodies are exercised,
without loading unrelated geometry/Qt classes that require FreeCAD.
Run: python3 -m unittest discover -s tests -v
Set CFDOF_MACOS_INTEGRATION=1 to also exercise the installed native OpenFOAM app.
"""

import ast
import glob
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from CfdOF import CfdDependencyData, CfdMacOS


def platform_functions():
    names = {"getFoamRuntime", "makeRunCommand", "detectFoamDir", "findInDefaultPaths",
             "getParaviewExecutable", "getGmshExecutable"}
    tree = ast.parse((ROOT / "CfdOF" / "CfdTools.py").read_text())
    tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    namespace = {
        "os": os, "glob": glob, "shutil": shutil, "subprocess": subprocess,
        "platform": types.SimpleNamespace(system=lambda: "Darwin"),
        "CfdMacOS": CfdMacOS, "CfdDependencyData": CfdDependencyData,
        "docker_container": types.SimpleNamespace(usedocker=False),
        "FreeCAD": types.SimpleNamespace(Console=types.SimpleNamespace(PrintMessage=lambda text: None),
                                         getHomePath=lambda: "/nonexistent/FreeCAD"),
        "getFoamDir": lambda: "/Applications/OpenFOAM-v2406.app",
        "getParaviewPath": lambda: "", "getGmshPath": lambda: "",
        "translatePath": lambda path, **kwargs: path,
    }
    exec(compile(tree, str(ROOT / "CfdOF" / "CfdTools.py"), "exec"), namespace)
    return namespace


class MacOSRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tools = platform_functions()

    def app(self):
        app = self.root / "OpenFOAM ' native.app"
        launcher = app / "Contents/Resources/etc/openfoam"
        launcher.parent.mkdir(parents=True)
        launcher.write_text('#!/bin/bash\nexec /bin/bash "$@"\n')
        launcher.chmod(0o755)
        return app

    def test_bundle_runtime_and_command_use_launcher(self):
        app = self.app()
        self.tools["getFoamDir"] = lambda: str(app)
        self.assertEqual(self.tools["getFoamRuntime"](), "MacOSApp")
        command = self.tools["makeRunCommand"]("printf native")
        self.assertEqual(command[0], str(app / "Contents/Resources/etc/openfoam"))
        self.assertEqual(subprocess.check_output(command, text=True), "native")

    def test_directory_is_literal_and_failed_cd_stops_command(self):
        app = self.app()
        directory = self.root / "case $variable `echo wrong` ' with spaces"
        directory.mkdir()
        command = CfdMacOS.makeFoamCommand(str(app), "pwd", directory)
        self.assertEqual(subprocess.check_output(command, text=True).strip(), str(directory))
        command = CfdMacOS.makeFoamCommand(str(app), "printf SHOULD_NOT_RUN", directory / "absent")
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_source_env_false_does_not_launch_app(self):
        app = self.app()
        command = CfdMacOS.makeFoamCommand(str(app), "printf clean", source_env=False)
        self.assertEqual(command[:2], ["/bin/bash", "-c"])
        self.assertEqual(subprocess.check_output(command, text=True), "clean")

    def test_native_source_and_bundled_tools_with_minimal_path(self):
        source = self.root / "OpenFOAM ' source"
        (source / "etc").mkdir(parents=True)
        (source / "env/bin").mkdir(parents=True)
        (source / "etc/bashrc").write_text("export WM_PROJECT_VERSION=vtest\n")
        mpi = source / "env/bin/mpiexec"
        mpi.write_text("#!/bin/sh\nprintf bundled-mpi\n")
        mpi.chmod(0o755)
        self.tools["getFoamDir"] = lambda: str(source)
        self.assertEqual(self.tools["getFoamRuntime"](), "Posix")
        command = self.tools["makeRunCommand"]('printf "%s:" "$WM_PROJECT_VERSION"; mpiexec')
        result = subprocess.check_output(command, text=True, env={"PATH": "/usr/bin:/bin"})
        self.assertEqual(result, "vtest:bundled-mpi")

    def test_darwin_detects_inherited_native_installation(self):
        native = self.root / "OpenFOAM-native"
        (native / "etc").mkdir(parents=True)
        (native / "etc/bashrc").touch()
        with patch.dict(os.environ, {"WM_PROJECT_DIR": str(native)}):
            self.assertEqual(self.tools["detectFoamDir"](), str(native))

    def test_darwin_empty_or_invalid_environment_uses_defaults(self):
        app = self.app()
        defaults = types.SimpleNamespace(FOAM_DIR_DEFAULTS={"Darwin": [str(app)]})
        self.tools["CfdDependencyData"] = defaults
        for value in ("", str(self.root / "absent")):
            with self.subTest(value=value), patch.dict(os.environ, {"WM_PROJECT_DIR": value}):
                self.assertEqual(self.tools["detectFoamDir"](), str(app))

    def test_paraview_bundle_and_pvpython_paths(self):
        self.tools["getParaviewPath"] = lambda: "/Applications/ParaView 5.app/"
        executable = self.tools["getParaviewExecutable"]()
        self.assertEqual(executable, "/Applications/ParaView 5.app/Contents/MacOS/paraview")
        self.assertEqual(CfdMacOS.paraviewPythonExecutable(executable),
                         "/Applications/ParaView 5.app/Contents/bin/pvpython")
        self.assertEqual(CfdMacOS.paraviewPythonExecutable("/opt/homebrew/bin/paraview"),
                         "/opt/homebrew/bin/pvpython")

    def test_gmsh_is_detected_without_shell_path(self):
        executable = self.root / "gmsh"
        executable.touch()
        executable.chmod(0o755)
        self.tools["getFoamRuntime"] = lambda: "MacOSApp"
        self.tools["CfdDependencyData"] = types.SimpleNamespace(
            GMSH_PATH_DEFAULTS={"Darwin": [str(executable)]})
        with patch.dict(os.environ, {"PATH": "/usr/bin:/bin"}):
            self.assertEqual(self.tools["getGmshExecutable"](), str(executable))
        self.tools["getGmshPath"] = lambda: "/Applications/Gmsh.app"
        self.assertEqual(self.tools["getGmshExecutable"](), "/Applications/Gmsh.app/Contents/MacOS/gmsh")

    def test_docker_runtime_is_preserved(self):
        self.tools["docker_container"].usedocker = True
        self.assertEqual(self.tools["getFoamRuntime"](), "PosixDocker")

    def test_linux_command_is_unchanged(self):
        self.tools["platform"] = types.SimpleNamespace(system=lambda: "Linux")
        self.tools["getFoamRuntime"] = lambda: "Posix"
        self.tools["getFoamDir"] = lambda: "/opt/openfoam"
        self.assertEqual(self.tools["makeRunCommand"]("simpleFoam", "/tmp/case"),
                         ["bash", "-c", 'source "/opt/openfoam/etc/bashrc" && cd "/tmp/case" && simpleFoam'])


@unittest.skipUnless(platform.system() == "Darwin" and os.environ.get("CFDOF_MACOS_INTEGRATION") == "1",
                     "Set CFDOF_MACOS_INTEGRATION=1 to test installed OpenFOAM")
class NativeOpenFoamTests(unittest.TestCase):
    def test_installed_app_and_mpi_with_finder_path(self):
        app = os.environ.get("CFDOF_OPENFOAM_APP", "/Applications/OpenFOAM-v2406.app")
        tools = platform_functions()
        tools["getFoamDir"] = lambda: app
        self.assertEqual(tools["getFoamRuntime"](), "MacOSApp")
        command = tools["makeRunCommand"](
            'printf "VERSION=%s\\nPROJECT=%s\\n" "$WM_PROJECT_VERSION" "$WM_PROJECT_DIR"; '
            'command -v simpleFoam; command -v mpiexec; simpleFoam -help')
        env = dict(os.environ, PATH="/usr/bin:/bin:/usr/sbin:/sbin")
        result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=45)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("VERSION=v", result.stdout)
        self.assertIn("/env/bin/mpiexec", result.stdout)
        self.assertIn("simpleFoam", result.stdout)


if __name__ == "__main__":
    unittest.main()
