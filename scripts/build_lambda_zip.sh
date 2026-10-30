#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 /absolute/path/to/lambda.zip" >&2
  exit 1
fi
case "$1" in /*) ;; *) echo "Output path must be absolute" >&2; exit 1;; esac

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/mcdr-lambda.XXXXXXXX")
trap 'rm -rf "$tmp_dir"' EXIT HUP INT TERM
python3 -m pip install --disable-pip-version-check --no-compile --only-binary=:all: \
  --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --abi cp312 \
  --target "$tmp_dir/packages" -r "$repo_dir/requirements-lambda.txt"

python3 - "$repo_dir" "$tmp_dir/packages" "$1" <<'PY'
import pathlib
import sys
import zipfile

repo, packages, output = map(pathlib.Path, sys.argv[1:])
with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(packages.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and not path.is_symlink():
            archive.write(path, path.relative_to(packages))
    for path in sorted((repo / "app").rglob("*.py")):
        if "tests" not in path.parts and "__pycache__" not in path.parts and not path.is_symlink():
            archive.write(path, path.relative_to(repo))
print("Lambda ZIP hazırlandı:", output)
PY
