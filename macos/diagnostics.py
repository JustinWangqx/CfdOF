#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-or-later
"""Inspect the native macOS CFD runtime without importing FreeCAD or changing preferences."""

import argparse
from datetime import datetime, timezone
import glob
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))
from CfdOF import CfdDependencyData, CfdMacOS


def default_path(defaults):
    for pattern in defaults.get("Darwin", []):
        matches = sorted(glob.glob(os.path.expandvars(os.path.expanduser(pattern))))
        if matches:
            return matches[-1]
    return None


def probe(argv, timeout, environment):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, errors="replace",
                                timeout=timeout, env=environment)
        return {"command": argv, "exit_code": result.returncode,
                "stdout": result.stdout[-6000:].strip(), "stderr": result.stderr[-3000:].strip()}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"command": argv, "exit_code": None, "error": str(error)}


def inspect(args):
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system": {"platform": platform.system(), "macos": platform.mac_ver()[0],
                   "architecture": platform.machine(), "python": platform.python_version()},
        "package": str(PACKAGE_ROOT), "openfoam": {}, "tools": {}, "warnings": [],
        "scope": "Command-line diagnostics only; FreeCAD GUI and CFD simulation are not exercised.",
    }
    if platform.system() != "Darwin":
        report["warnings"].append("This diagnostic is intended for macOS.")

    environment = dict(os.environ)
    # A Python launched inside an application must not force its Python runtime
    # onto ParaView or another application bundle.
    for key in ("PYTHONHOME", "PYTHONPATH"):
        environment.pop(key, None)

    installation = args.openfoam
    if not installation:
        inherited = os.environ.get("WM_PROJECT_DIR")
        if inherited and os.path.isfile(os.path.join(inherited, "etc", "bashrc")):
            installation = inherited
        else:
            installation = default_path(CfdDependencyData.FOAM_DIR_DEFAULTS)
    if installation:
        installation = os.path.abspath(os.path.expanduser(installation))
    runtime = None
    if installation and CfdMacOS.openFoamAppLauncher(installation):
        runtime = "MacOSApp"
    elif installation and os.path.isfile(os.path.join(installation, "etc", "bashrc")):
        runtime = "Posix"

    report["openfoam"].update({"installation": installation, "runtime": runtime})
    if runtime:
        names = ("blockMesh", "snappyHexMesh", "simpleFoam", "icoFoam", "mpiexec", "wmake",
                 "cartesianMesh", "hisa")
        command = 'printf "WM_PROJECT_VERSION=%s\\nWM_PROJECT_DIR=%s\\n" "$WM_PROJECT_VERSION" "$WM_PROJECT_DIR"; '
        for name in names:
            command += 'printf "{}=%s\\n" "$(command -v {} || true)"; '.format(name, shlex.quote(name))
        result = probe(CfdMacOS.makeFoamCommand(installation, command), args.timeout, environment)
        report["openfoam"]["probe"] = result
        values = {}
        if result.get("exit_code") == 0:
            for line in result["stdout"].splitlines():
                key, separator, value = line.partition("=")
                if separator and key in ("WM_PROJECT_VERSION", "WM_PROJECT_DIR") + names:
                    values[key] = value
        report["openfoam"]["version"] = values.get("WM_PROJECT_VERSION")
        report["openfoam"]["project_directory"] = values.get("WM_PROJECT_DIR")
        for name in names:
            report["tools"][name] = {"path": values.get(name) or None}
        for name in ("cartesianMesh", "hisa"):
            if values.get(name):
                result = probe(CfdMacOS.makeFoamCommand(installation, name + " -version"),
                               args.timeout, environment)
                report["tools"][name]["version_probe"] = result
            else:
                report["warnings"].append(name + " not found; its dependent features are unavailable.")
        if not report["openfoam"]["version"]:
            report["warnings"].append("OpenFOAM environment could not be activated.")
    else:
        report["warnings"].append("No recognised native OpenFOAM installation found.")

    paraview = default_path(CfdDependencyData.PARAVIEW_PATH_DEFAULTS) or shutil.which("paraview")
    paraview = CfdMacOS.bundleExecutable(paraview, "paraview")
    gmsh = shutil.which("gmsh") or default_path(CfdDependencyData.GMSH_PATH_DEFAULTS)
    for name, executable, flag in (("paraview", paraview, "--version"), ("gmsh", gmsh, "-version")):
        report["tools"][name] = {"path": executable}
        if executable:
            result = probe([executable, flag], args.timeout, environment)
            report["tools"][name]["version_probe"] = result
            if result.get("exit_code") != 0:
                report["warnings"].append(name + " exists but its version command failed.")
        else:
            report["warnings"].append(name + " not found.")
    if paraview:
        pvpython = CfdMacOS.paraviewPythonExecutable(paraview)
        report["tools"]["pvpython"] = {"path": pvpython, "exists": os.path.isfile(pvpython)}

    report["minimum_versions"] = {
        "gmsh": "{}.{}".format(CfdDependencyData.GMSH_MAJOR_VERSION_REQUIRED,
                               CfdDependencyData.GMSH_MINOR_VERSION_REQUIRED),
        "cfmesh": "{}.{}".format(CfdDependencyData.CF_MAJOR_VER_REQUIRED, CfdDependencyData.CF_MINOR_VER_REQUIRED),
        "hisa": "{}.{}.{}".format(CfdDependencyData.HISA_MAJOR_VER_REQUIRED,
                                  CfdDependencyData.HISA_MINOR_VER_REQUIRED, CfdDependencyData.HISA_PATCH_VER_REQUIRED),
    }
    # Discovery is distinct from a full workbench dependency check.
    report["ok"] = bool(report["openfoam"].get("version"))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--openfoam", help="Path to OpenFOAM.app or native OpenFOAM source directory")
    parser.add_argument("--json", default="cfdof-diagnostics.json", help="Output JSON path; '-' writes JSON to stdout")
    parser.add_argument("--timeout", type=float, default=45, help="Per-command timeout in seconds")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    report = inspect(args)
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json == "-":
        print(serialized, end="")
    else:
        target = Path(args.json).expanduser().absolute()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(serialized, encoding="utf-8")
        print("OpenFOAM:", report["openfoam"].get("runtime"), report["openfoam"].get("version"))
        for name, info in report["tools"].items():
            print("{}: {}".format(name, info.get("path") or "未找到"))
        for warning in report["warnings"]:
            print("提示:", warning)
        print("JSON:", target)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
