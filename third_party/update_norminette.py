#!/usr/bin/env python3
"""Fetch the official 42 norminette into third_party/norminette/.

The grader runs the real tool (https://github.com/42school/norminette, MIT), shipped inside the
kit so that every machine gives the verdict the school gives, with nothing to install: no pip, no
venv, no package manager. This script is for the maintainer who wants another version:

    python3 third_party/update_norminette.py            # the pinned version below
    python3 third_party/update_norminette.py 3.3.60     # a given version
    python3 third_party/update_norminette.py --wheel norminette-3.3.60-py3-none-any.whl

It needs Python 3 and nothing else. It downloads the wheel published on PyPI by 42school, checks
its sha256 against the one PyPI announces, and unpacks it. After an update, run
`python3 tests/test_norminette_official.py`: a new version may reject reference solutions that the
previous one accepted.
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

PINNED_VERSION = "3.3.60"
DEST = Path(__file__).resolve().parent / "norminette"


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310 (https URL built below)
        return resp.read()


def download_wheel(version: str) -> tuple[bytes, str, str]:
    meta = json.loads(fetch(f"https://pypi.org/pypi/norminette/{version}/json"))
    wheels = [u for u in meta["urls"] if u["packagetype"] == "bdist_wheel" and u["filename"].endswith("py3-none-any.whl")]
    if not wheels:
        raise SystemExit(f"norminette {version}: PyPI has no pure-Python wheel")
    wheel = wheels[0]
    data = fetch(wheel["url"])
    digest = hashlib.sha256(data).hexdigest()
    if digest != wheel["digests"]["sha256"]:
        raise SystemExit(f"sha256 mismatch for {wheel['filename']}: got {digest}, PyPI announces {wheel['digests']['sha256']}")
    return data, wheel["url"], digest


def unpack(data: bytes, source: str, digest: str) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        dist_info = sorted({n.split("/")[0] for n in names if n.split("/")[0].endswith(".dist-info")})
        if "norminette/__main__.py" not in names or len(dist_info) != 1:
            raise SystemExit("this archive is not a norminette wheel")
        for name in names:
            target = (DEST / name).resolve()
            if DEST.resolve() not in target.parents:
                raise SystemExit(f"unsafe path in the wheel: {name}")
        if DEST.exists():
            shutil.rmtree(DEST)
        DEST.mkdir(parents=True)
        archive.extractall(DEST)
    version = dist_info[0][len("norminette-"):-len(".dist-info")]
    (DEST / "SOURCE.txt").write_text(
        "The official 42 norminette, unmodified.\n"
        "project : https://github.com/42school/norminette (MIT, see the LICENSE in the dist-info folder)\n"
        f"version : {version}\n"
        f"wheel   : {source}\n"
        f"sha256  : {digest}\n"
        "update  : python3 third_party/update_norminette.py [version]\n",
        encoding="utf-8",
    )
    return version


def main(argv: list[str]) -> int:
    if argv[:1] in (["-h"], ["--help"]):
        print(__doc__)
        return 0
    if argv[:1] == ["--wheel"]:
        if len(argv) != 2:
            raise SystemExit("usage: update_norminette.py --wheel <file.whl>")
        data = Path(argv[1]).read_bytes()
        source, digest = Path(argv[1]).name, hashlib.sha256(data).hexdigest()
    else:
        if len(argv) > 1:
            raise SystemExit("usage: update_norminette.py [version]")
        data, source, digest = download_wheel(argv[0] if argv else PINNED_VERSION)
    version = unpack(data, source, digest)
    print(f"norminette {version} unpacked in {DEST}")
    print(f"sha256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
