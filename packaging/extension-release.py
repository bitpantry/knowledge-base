"""Package an extension's tracked software, never its working records."""
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"core"))
from update import encode
from vault import RECEIPT, extension_receipt, load_extension, managed_extension, package_name


def git(*args):
    return subprocess.check_output(["git","-C",str(ROOT),*args])


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: python3 -B packaging/extension-release.py SLUG OUTPUT_DIRECTORY")
    slug, out = sys.argv[1:]
    output = Path(out)/package_name(slug)
    commit = git("rev-parse","HEAD").decode().strip()
    prefix = f"extensions/{slug}/"
    files = {}
    for line in git("ls-tree","-r","-z",commit,"--",prefix).decode().split("\0"):
        if not line:
            continue
        meta, name = line.split("\t",1)
        mode, kind, oid = meta.split()
        rel = name.removeprefix(prefix)
        if not managed_extension(rel) or mode not in {"100644","100755"} or kind != "blob":
            sys.exit(f"Refusing unexpected tracked extension path: {name}")
        files[rel] = git("cat-file","blob",oid)
    receipt = extension_receipt(slug,commit,files)
    with zipfile.ZipFile(output,"x",compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(RECEIPT,encode(receipt))
        for rel,data in files.items():
            z.writestr(rel,data)
    load_extension(output.read_bytes(),slug)


if __name__ == "__main__":
    main()
