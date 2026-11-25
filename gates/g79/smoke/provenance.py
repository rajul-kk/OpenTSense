"""Match the pinned ORFS image's Ibex and design config to a public ORFS tree."""
import hashlib
import json
import tarfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = "https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts"
COMMIT = "f52850725e4ffe4030175328aa976cd8fb4943b9"
ORFS = "openroad/orfs@sha256:55266bc72fd67238407fa0c60da5a7f83c25ea14123829df769437d0dd0649ed"
PATHS = ("designs/src/ibex_sv/", "designs/asap7/ibex/")
RAW = f"https://raw.githubusercontent.com/The-OpenROAD-Project/OpenROAD-flow-scripts/{COMMIT}/flow"


def match(item):
    name, payload = item
    with urllib.request.urlopen(f"{RAW}/{name}", timeout=30) as response:
        if response.read() != payload:
            raise ValueError(f"image source differs from upstream: {name}")


def main():
    archive = HERE / "image-source.tar"
    with tarfile.open(archive) as source:
        files = {item.name: source.extractfile(item).read() for item in source if item.isfile()}
    if not all(any(name.startswith(prefix) for name in files) for prefix in PATHS):
        raise ValueError("image source inventory missing the RTL or platform files")
    if any(not name.startswith(PATHS) or ".." in Path(name).parts for name in files):
        raise ValueError("unexpected path in image source archive")
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(match, files.items()))
    out = HERE / "source"
    out.mkdir()
    for name, payload in files.items():
        dst = out / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(payload)
    record = {"orfs_image": ORFS, "orfs_repository": REPO, "matching_source_commit": COMMIT,
              "image_build_commit_attested": False, "upstream_raw_base": RAW,
              "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
              "files": {name: {"sha256": hashlib.sha256(data).hexdigest()}
                        for name, data in sorted(files.items())}}
    (HERE / "source.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"ORFS image and {COMMIT} match across all {len(files)} Ibex source and platform files")


if __name__ == "__main__":
    main()
