#!/bin/bash
# SPDX-License-Identifier: LGPL-3.0-or-later
# Install this portable CfdOF package; keep any existing installation as a backup.
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "$0")" && pwd -P)"
package_root="$(cd -- "$script_dir/.." && pwd -P)"
mod_dir="${CFDOF_MOD_DIR:-}"
backup_path=""
staging_dir=""
probe_dir=""

if [ "$(uname -s)" != Darwin ]; then
    echo "此安装脚本仅用于 macOS。" >&2
    exit 1
fi
if [ ! -f "$package_root/Init.py" ] || [ ! -f "$package_root/CfdOF/CfdMacOS.py" ]; then
    echo "安装包不完整：请保持 macos 文件夹与 CfdOF 源码的相对位置。" >&2
    exit 1
fi
if [ "$#" -ne 0 ]; then
    echo "用法：直接运行此脚本；自定义 Mod 目录请设置 CFDOF_MOD_DIR。" >&2
    exit 1
fi

cleanup() {
    if [ -n "$staging_dir" ] && [ -d "$staging_dir" ]; then
        rm -rf -- "$staging_dir"
    fi
    if [ -n "$probe_dir" ] && [ -d "$probe_dir" ]; then
        rm -rf -- "$probe_dir"
    fi
}
trap cleanup EXIT

# Ask the installed FreeCAD which profile it uses. FreeCAD 1.1 can use
# a versioned directory after migrating an existing profile.
if [ -z "$mod_dir" ]; then
    for app in /Applications/FreeCAD.app "$HOME/Applications/FreeCAD.app"; do
        freecadcmd="$app/Contents/Resources/bin/freecadcmd"
        if [ -x "$freecadcmd" ]; then
            probe_dir="$(mktemp -d "${TMPDIR:-/tmp}/cfdof-profile.XXXXXX")"
            data_dir="$(
                printf '%s\n' 'print("__CFDOF_DATA__=" + FreeCAD.getUserAppDataDir())' 'exit()' |
                "$freecadcmd" --user-cfg "$probe_dir/user.cfg" --system-cfg "$probe_dir/system.cfg" |
                sed -n 's/^.*__CFDOF_DATA__=//p'
            )"
            if [[ "$data_dir" == /* && "$data_dir" != *$'\n'* ]]; then
                mod_dir="${data_dir%/}/Mod"
            fi
            break
        fi
    done
    if [ -z "$mod_dir" ]; then
        echo "无法识别 FreeCAD 的插件目录。请先安装 FreeCAD，或用 CFDOF_MOD_DIR 指定 Mod 目录。" >&2
        exit 1
    fi
fi

mkdir -p -- "$mod_dir"
mod_dir="$(cd -- "$mod_dir" && pwd -P)"
install_path="$mod_dir/CfdOF"
case "$package_root/" in
    "$install_path/"*)
        echo "此安装包已经位于目标 CfdOF 目录，无需再次安装。"
        exit 0
        ;;
esac

# Copy completely before touching the current add-on. The staging directory is
# on the destination filesystem, so the final rename is local and atomic.
staging_dir="$(mktemp -d "$mod_dir/.CfdOF-install.XXXXXX")"
/usr/bin/ditto "$package_root" "$staging_dir/CfdOF"

if [ -e "$install_path" ] || [ -L "$install_path" ]; then
    # Keep previous workbenches outside Mod, where FreeCAD would also load them.
    backup_dir="$mod_dir/../CfdOF-backups"
    mkdir -p -- "$backup_dir"
    backup_path="$backup_dir/CfdOF-$(date +%Y%m%d-%H%M%S)-$$"
    if [ -e "$backup_path" ] || [ -L "$backup_path" ]; then
        echo "备份路径已存在，安装已停止：$backup_path" >&2
        exit 1
    fi
    mv -- "$install_path" "$backup_path"
fi

if ! mv -- "$staging_dir/CfdOF" "$install_path"; then
    if [ -n "$backup_path" ]; then
        mv -- "$backup_path" "$install_path"
    fi
    echo "安装失败，原有插件已保留。" >&2
    exit 1
fi

echo "已安装：$install_path"
if [ -n "$backup_path" ]; then
    echo "原有插件备份：$backup_path"
fi
echo "请重启 FreeCAD，选择 CfdOF 工作台。"
echo "在 FreeCAD 设置 → CfdOF 中检查依赖；OpenFOAM 路径可选择 OpenFOAM-v2406.app。"
echo "本脚本没有修改 FreeCAD 偏好设置，也没有安装 OpenFOAM、ParaView、cfMesh 或 HiSA。"
