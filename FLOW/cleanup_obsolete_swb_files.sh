#!/usr/bin/env bash
# Remove every non-whitelisted regular file from one Sentaurus Workbench
# project directory. Compatible with Bash 4.2. The default is a safe preview.

set -uo pipefail

usage() {
    cat <<'EOF'
Usage:
  cleanup_obsolete_swb_files.sh [--target DIRECTORY] [--execute]

Options:
  --target DIRECTORY  SWB project directory to inspect (default: script directory).
  --execute           Permanently delete files not in the built-in allowlist.
                      Without it, preview only.
  -h, --help          Show this help.
EOF
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
target_dir="$script_dir"
execute=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)
            [[ $# -ge 2 ]] || { echo 'Error: --target requires a directory.' >&2; exit 2; }
            target_dir="$2"
            shift 2
            ;;
        --execute)
            execute=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Error: unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

[[ -d "$target_dir" ]] || { echo "Error: directory not found: $target_dir" >&2; exit 2; }
target_dir="$(cd "$target_dir" && pwd -P)"

keep_files=(
    'c_dvs.cmd'
    'c_dvs.prf'
    'cleanup_obsolete_swb_files.sh'
    'cmlog.txt'
    'gadvscens.dat'
    'gcomments.dat'
    'gscens.dat'
    'gtree.dat'
    'gtree.dat.backup'
    'gvars.dat'
    'raphaelfx_1_rcfx.cmd'
    'raphaelfx_1_rcfx.prf'
    'raphaelfx_2_rcfx.cmd'
    'raphaelfx_2_rcfx.prf'
    'r_dvs.cmd'
    'r_dvs.prf'
    'SVisualTcl.log'
    'SVisualTcl.log.BAK'
    'test_C_bnd.tdr'
    'test_C_msh.cmd'
    'test_C_msh.log'
    'test_C_msh.tdr'
    'test_R_bnd.tdr'
    'test_R_msh.cmd'
    'test_R_msh.log'
    'test_R_msh.tdr'
)

# No recursive search: only non-hidden regular files directly in the selected
# project folder are handled. Hidden SWB metadata (for example .project and
# .database), directories, and their contents are never removed.
matches=()
for file in "$target_dir"/*; do
    [[ -f "$file" ]] || continue

    should_keep=0
    for keep_file in "${keep_files[@]}"; do
        if [[ "${file##*/}" == "$keep_file" ]]; then
            should_keep=1
            break
        fi
    done

    [[ $should_keep -eq 1 ]] || matches+=("$file")
done

if [[ ${#matches[@]} -eq 0 ]]; then
    echo "No non-whitelisted files found in: $target_dir"
    exit 0
fi

echo "Files to remove (${#matches[@]}) in: $target_dir"
printf '  %s\n' "${matches[@]##*/}"

if [[ $execute -eq 0 ]]; then
    echo
    echo 'Preview only: no files were removed.'
    echo 'Run again with --execute to permanently delete the files above.'
    exit 0
fi

for file in "${matches[@]}"; do
    rm -f -- "$file"
done
echo "Removed ${#matches[@]} file(s)."
