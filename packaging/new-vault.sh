#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ] || [ -z "$1" ]; then
  echo "Usage: bash packaging/new-vault.sh /path/to/new-vault" >&2
  exit 2
fi
dest=$1
case "$dest" in /*) ;; *) dest="$PWD/$dest";; esac
if [ -e "$dest" ] || [ -L "$dest" ]; then
  echo "Destination already exists: $dest" >&2
  exit 2
fi
root=$(cd -- "$(dirname -- "$0")/.." && pwd -P)
revision=$(git -C "$root" rev-parse --verify HEAD)
archive=$(mktemp -d "${TMPDIR:-/tmp}/km-new-vault.XXXXXX")
trap 'rm -f -- "$archive/core.tar" "$archive/README.md" "$archive/gitignore"; rmdir -- "$archive"' EXIT
git -C "$root" archive --format=tar "$revision" > "$archive/core.tar"
git -C "$root" show "$revision:packaging/vault-README.md" > "$archive/README.md"
git -C "$root" show "$revision:packaging/vault.gitignore" > "$archive/gitignore"

mkdir -- "$dest"
tar -xf "$archive/core.tar" -C "$dest"
cp -- "$archive/README.md" "$dest/README.md"
cp -- "$archive/gitignore" "$dest/.gitignore"
printf 'Created vault at %s from %s\n' "$dest" "$revision"
