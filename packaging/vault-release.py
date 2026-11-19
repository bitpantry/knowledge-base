"""Build the published updater asset from a fresh committed vault export."""
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
from update import MANIFEST, decode, encode, local_files, manifest, unbundle


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: python3 -B packaging/vault-release.py FRESH_VAULT OUTPUT.zip")
    root, output = map(Path, sys.argv[1:])
    receipt = decode((root / MANIFEST).read_bytes())
    files = local_files(root)
    if manifest(receipt["commit"], files) != receipt:
        sys.exit("Export does not match its installed-core manifest")
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(MANIFEST, encode(receipt))
        for name, data in files.items():
            z.writestr(name, data)
    unbundle(output.read_bytes())


if __name__ == "__main__":
    main()
