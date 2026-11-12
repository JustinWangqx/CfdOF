#!/bin/bash
# SPDX-License-Identifier: LGPL-3.0-or-later
# Build the native cfMesh and HiSA used by CfdOF on OpenFOAM-v2406.app.
set -euo pipefail

cfmesh_ref=afe2bbabd973d85ccdf2002437c712b9dae8a77c
cfmesh_url="https://gitlab.com/api/v4/projects/hisa%2Fcfmesh/repository/archive.tar.gz?sha=$cfmesh_ref"
cfmesh_sha=07f5cb8de39156dc33f6cd47402c21c9915fa66bdd4a5cb2c674799fb44d93ab
# GitLab's master archive of the same revision has a different directory prefix.
cfmesh_master_sha=d0b999d8445dcdfe0ccac0a59308b80159967d1134c06f2fd9df4648a7f41a4f
hisa_url=https://master.dl.sourceforge.net/project/hisa/hisa-master.zip?viasf=1
hisa_sha=5c99093e67defb7f8af0ce967bd0d2907d7ccfaa45bf8bf982e84646dad144e6

fail() {
    echo "$*" >&2
    exit 1
}

usage() {
    cat <<'EOF'
Usage: install-dependencies.command [options]
Build cfMesh-CfdOF 1.33 and HiSA 1.13.4 for native OpenFOAM-v2406.app.

  --openfoam-app PATH      Path to OpenFOAM-v2406.app
  --jobs N                 Number of concurrent compiler jobs
  --cfmesh-archive PATH    Use a local copy of the verified cfMesh archive
  --hisa-archive PATH      Use a local copy of the verified HiSA archive
  --prefix PATH            Install into PATH/bin and PATH/lib (no whitespace)
  --help                   Show this help

By default, install to the OpenFOAM environment's user bin and lib.
Requires Xcode Command Line Tools and network access or both local archives.
EOF
}

get_archive() {
    local url="$1" supplied="$2" output="$3" expected="$4" alternate="${5:-}"
    local actual
    if [ -n "$supplied" ]; then
        /bin/cp -- "$supplied" "$output"
    else
        /usr/bin/curl --fail --location --show-error --silent --retry 2 \
            --proto '=https' --proto-redir '=https' --connect-timeout 15 --max-time 600 \
            "$url" --output "$output"
    fi
    actual="$(/usr/bin/shasum -a 256 "$output")"
    actual="${actual%% *}"
    if [ "$actual" != "$expected" ] && [ "$actual" != "$alternate" ]; then
        fail "SHA-256 mismatch for $(basename -- "$output"). Expected $expected, got $actual."
    fi
}

# Stage replacement files and save the originals before modifying either target.
prepare_install() {
    local source_dir="$1" target_dir="$2" temporary="$3" backup="$4" mode="$5"
    local source name
    /usr/bin/find "$source_dir" -maxdepth 1 -type f -print > "$temporary/manifest"
    while IFS= read -r source; do
        name="${source##*/}"
        if [ -d "$target_dir/$name" ]; then
            fail "Expected a file at $target_dir/$name. Please move that directory first."
        fi
        /usr/bin/install -m "$mode" "$source" "$temporary/$name"
        if [ -e "$target_dir/$name" ] || [ -L "$target_dir/$name" ]; then
            /bin/mkdir -p "$backup"
            /bin/cp -pP "$target_dir/$name" "$backup/$name"
        fi
    done < "$temporary/manifest"
}

commit_install() {
    local kind="$1" target_dir="$2" temporary="$3"
    local source name
    while IFS= read -r source; do
        name="${source##*/}"
        /bin/mv -fh "$temporary/$name" "$target_dir/$name"
        installed+=("$kind/$name")
    done < "$temporary/manifest"
}

rollback_install() {
    local status="$?" item kind name target backup
    trap - EXIT
    set +e
    if [ "$status" -ne 0 ]; then
        # Roll back only the entries that this invocation replaced.
        for item in "${installed[@]+"${installed[@]}"}"; do
            kind="${item%%/*}"
            name="${item#*/}"
            if [ "$kind" = bin ]; then
                target="$target_bin"
                backup="$bin_backup"
            else
                target="$target_lib"
                backup="$lib_backup"
            fi
            if [ -e "$backup/$name" ] || [ -L "$backup/$name" ]; then
                /bin/mv -fh "$backup/$name" "$target/$name" ||
                    echo "Restore $backup/$name manually." >&2
            else
                /bin/rm -f "$target/$name"
            fi
        done
    fi
    [ -z "$bin_temporary" ] || /bin/rm -rf "$bin_temporary"
    [ -z "$lib_temporary" ] || /bin/rm -rf "$lib_temporary"
    /bin/rmdir "$lock" 2>/dev/null || true
    exit "$status"
}

build_and_install() {
    local build_dir="$1" jobs="$2" prefix="$3"
    target_bin="${FOAM_USER_APPBIN:-}"
    target_lib="${FOAM_USER_LIBBIN:-}"
    if [ "${WM_PROJECT_VERSION:-}" != v2406 ] || [[ "${WM_OPTIONS:-}" != darwin* ]]; then
        fail "Expected native OpenFOAM v2406 (found ${WM_PROJECT_VERSION:-unknown}, ${WM_OPTIONS:-unknown})."
    fi
    if ! command -v wmake >/dev/null || ! /usr/bin/xcode-select -p >/dev/null 2>&1; then
        fail "OpenFOAM wmake and Xcode Command Line Tools are required."
    fi
    if [ -n "$prefix" ]; then
        target_bin="$prefix/bin"
        target_lib="$prefix/lib"
    fi
    if [[ "$target_bin" != /* || "$target_lib" != /* || "$target_bin" = "$target_lib" ]]; then
        fail "OpenFOAM did not report separate absolute user bin and lib paths."
    fi
    if [[ "$target_bin" == *[[:space:]]* || "$target_lib" == *[[:space:]]* ]]; then
        fail "OpenFOAM user bin and lib paths must not contain whitespace."
    fi
    cd -- "$build_dir"

    local project log original_dyld="${DYLD_LIBRARY_PATH:-}"
    export FOAM_USER_APPBIN="$build_dir/bin"
    export FOAM_USER_LIBBIN="$build_dir/lib"
    export WM_NCOMPPROCS="$jobs"
    export PATH="$FOAM_USER_APPBIN:$PATH"
    export DYLD_LIBRARY_PATH="$FOAM_USER_LIBBIN${original_dyld:+:$original_dyld}"
    /bin/mkdir "$FOAM_USER_APPBIN" "$FOAM_USER_LIBBIN"
    for project in cfmesh hisa-master; do
        log="$build_dir/$project.log"
        echo "Building $project with $jobs jobs. Log: $log"
        if ! (cd -- "$build_dir/$project" && bash -e ./Allwmake) > "$log" 2>&1; then
            /usr/bin/tail -40 "$log" >&2
            fail "$project build failed."
        fi
    done

    local program version
    for program in cartesianMesh cartesian2DMesh surfaceFeatureEdges hisa; do
        [ -x "$FOAM_USER_APPBIN/$program" ] || fail "Build did not produce $program."
    done
    version="$("$FOAM_USER_APPBIN/cartesianMesh" -version 2>&1)" || fail "$version"
    [[ "$version" == *'1.33'* ]] || fail "Unexpected cfMesh version: $version"
    version="$("$FOAM_USER_APPBIN/hisa" -version 2>&1)" || fail "$version"
    [[ "$version" == *'1.13.4'* ]] || fail "Unexpected HiSA version: $version"

    # Backups stay beside each set of files. A lock prevents two invocations
    # from interleaving replacements in the same OpenFOAM environment.
    local id="${build_dir##*/}"
    lock="$target_bin/.cfdof-dependencies.lock"
    bin_backup="$target_bin/.cfdof-backups/$id"
    lib_backup="$target_lib/.cfdof-backups/$id"
    bin_temporary=""
    lib_temporary=""
    installed=()
    /bin/mkdir -p "$target_bin" "$target_lib"
    /bin/mkdir "$lock" || fail "Another installation is active or left a lock at $lock."
    trap rollback_install EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    bin_temporary="$(/usr/bin/mktemp -d "$target_bin/.cfdof-install.XXXXXXXX")"
    lib_temporary="$(/usr/bin/mktemp -d "$target_lib/.cfdof-install.XXXXXXXX")"
    prepare_install "$FOAM_USER_APPBIN" "$target_bin" "$bin_temporary" "$bin_backup" 755
    prepare_install "$FOAM_USER_LIBBIN" "$target_lib" "$lib_temporary" "$lib_backup" 755
    commit_install lib "$target_lib" "$lib_temporary"
    commit_install bin "$target_bin" "$bin_temporary"
    export DYLD_LIBRARY_PATH="$target_lib${original_dyld:+:$original_dyld}"
    "$target_bin/cartesianMesh" -version > "$build_dir/cfmesh-installed.log" 2>&1 ||
        fail "$(cat "$build_dir/cfmesh-installed.log")"
    "$target_bin/hisa" -version > "$build_dir/hisa-installed.log" 2>&1 ||
        fail "$(cat "$build_dir/hisa-installed.log")"
    echo "Installed cfMesh-CfdOF 1.33 and HiSA 1.13.4."
    echo "Executables: $target_bin"
    echo "Libraries: $target_lib"
    if [ -d "$bin_backup" ]; then echo "Executable backups: $bin_backup"; fi
    if [ -d "$lib_backup" ]; then echo "Library backups: $lib_backup"; fi

    exit 0
}

if [ "${1:-}" = --build ]; then
    shift
    build_and_install "$@"
fi

app=""
prefix=""
jobs=""
cfmesh_archive=""
hisa_archive=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --help|-h) usage; exit 0 ;;
        --openfoam-app|--prefix|--jobs|--cfmesh-archive|--hisa-archive)
            [ "$#" -ge 2 ] && [ -n "$2" ] || fail "Missing value for $1."
            case "$1" in
                --openfoam-app) app="$2" ;;
                --prefix) prefix="$2" ;;
                --jobs) jobs="$2" ;;
                --cfmesh-archive) cfmesh_archive="$2" ;;
                --hisa-archive) hisa_archive="$2" ;;
            esac
            shift 2
            ;;
        *) usage >&2; fail "Unknown option: $1." ;;
    esac
done
[ "$(/usr/bin/uname -s)" = Darwin ] || fail "This installer requires macOS."
if [ -z "$app" ]; then
    for candidate in /Applications/OpenFOAM-v2406.app "$HOME/Applications/OpenFOAM-v2406.app"; do
        if [ -x "$candidate/Contents/Resources/etc/openfoam" ]; then
            app="$candidate"
            break
        fi
    done
fi
[ -n "$app" ] && [ -x "$app/Contents/Resources/etc/openfoam" ] ||
    fail "Install OpenFOAM-v2406.app first or specify it with --openfoam-app."
launcher="$(cd -- "$app" && pwd -P)/Contents/Resources/etc/openfoam"
script="$(cd -- "$(dirname -- "$0")" && pwd -P)/$(basename -- "$0")"
if [ -n "$prefix" ] && [[ "$prefix" != /* ]]; then prefix="$PWD/$prefix"; fi
if [[ "$prefix" == *[[:space:]]* ]]; then
    fail "OpenFOAM cannot run executables installed in a path containing whitespace."
fi
if [ -z "$jobs" ]; then
    jobs="$(/usr/sbin/sysctl -n hw.logicalcpu 2>/dev/null || echo 2)"
    if [ "$jobs" -gt 6 ]; then jobs=6; fi
fi
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || fail "--jobs requires a positive integer."
/usr/bin/xcode-select -p >/dev/null 2>&1 || fail "Install Xcode Command Line Tools with xcode-select --install."

# wmake does not handle whitespace in build paths. Keep the temporary tree
# in a fixed location independent of the location of the add-on or archives.
build_dir="$(/usr/bin/mktemp -d /tmp/cfdof-dependencies.XXXXXXXX)"
trap 'status=$?; if [ "$status" -eq 0 ]; then /bin/rm -rf "$build_dir"; else echo "Build files and logs: $build_dir" >&2; fi' EXIT
echo "Verifying cfMesh-CfdOF 1.33 and HiSA 1.13.4 source archives..."
get_archive "$cfmesh_url" "$cfmesh_archive" "$build_dir/cfmesh.tgz" "$cfmesh_sha" "$cfmesh_master_sha"
get_archive "$hisa_url" "$hisa_archive" "$build_dir/hisa.zip" "$hisa_sha"
/bin/mkdir "$build_dir/cfmesh"
/usr/bin/tar -xzf "$build_dir/cfmesh.tgz" --strip-components 1 -C "$build_dir/cfmesh"
/usr/bin/unzip -q "$build_dir/hisa.zip" -d "$build_dir"
# The launcher puts its bundled Bash on PATH. Using macOS system Bash here
# would strip DYLD_* variables needed to load OpenFOAM's dynamic libraries.
"$launcher" bash "$script" --build "$build_dir" "$jobs" "$prefix"
