# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CfdOF addon.

"""macOS application discovery and command construction, independent of FreeCAD."""

import os
import shlex


def openFoamAppLauncher(installation_path):
    """Return the native OpenFOAM.app launcher, without mounting its disk image."""
    launcher = os.path.join(installation_path, "Contents", "Resources", "etc", "openfoam")
    if os.path.isfile(launcher) and os.access(launcher, os.X_OK):
        return launcher
    return None


def makeFoamCommand(installation_path, cmd, directory=None, source_env=True):
    """Run a shell command using an app bundle or a native source installation.

    The app's launcher mounts the case-sensitive volume, retains it while running,
    and selects its bundled MPI and other tools. Merely sourcing etc/bashrc loses
    those steps. Source installations and already-mounted volumes remain supported.
    """
    command = cmd
    if directory:
        command = "cd -- {} && ".format(shlex.quote(os.fspath(directory))) + command
    if not source_env:
        return ["/bin/bash", "-c", command]

    launcher = openFoamAppLauncher(installation_path)
    if launcher:
        return [launcher, "-c", command]

    source = ""
    shell = "/bin/bash"
    if installation_path:
        env_bin = os.path.join(installation_path, "env", "bin")
        if os.path.isdir(env_bin):
            source += "export PATH={}:\"$PATH\"; ".format(shlex.quote(env_bin))
            bundled_bash = os.path.join(env_bin, "bash")
            if os.path.isfile(bundled_bash) and os.access(bundled_bash, os.X_OK):
                shell = bundled_bash
        bashrc = os.path.join(installation_path, "etc", "bashrc")
        source += "source {} && ".format(shlex.quote(bashrc))
    return [shell, "-c", source + command]


def bundleExecutable(path, executable):
    """Accept either a .app bundle selected in preferences or an executable."""
    if path and os.path.normpath(path).lower().endswith(".app"):
        return os.path.join(os.path.normpath(path), "Contents", "MacOS", executable)
    return path


def paraviewPythonExecutable(paraview):
    """ParaView.app keeps pvpython in Contents/bin, beside the MacOS directory."""
    executable_dir = os.path.dirname(paraview)
    if os.path.basename(executable_dir) == "MacOS":
        return os.path.join(os.path.dirname(executable_dir), "bin", "pvpython")
    return os.path.join(executable_dir, "pvpython")
