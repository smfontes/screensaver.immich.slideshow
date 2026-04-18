import os
import zipfile
import fnmatch
from pathlib import Path

def get_manifest_files(manifest_path="MANIFEST.in"):
    base_dir = Path(manifest_path).parent.resolve()
    files = set()
    prune_dirs = []

    with open(manifest_path, "r") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            cmd = parts[0]

            if cmd == "prune":
                prune_dirs.append(parts[1])

            elif cmd == "include":
                pattern = parts[1]
                for path in base_dir.glob(pattern):
                    if path.is_file():
                        files.add(path.relative_to(base_dir))

            elif cmd == "recursive-include":
                dir_path = base_dir / parts[1]
                patterns = parts[2:]

                for root, _, filenames in os.walk(dir_path):
                    for name in filenames:
                        if any(fnmatch.fnmatch(name, p) for p in patterns):
                            full_path = Path(root) / name
                            files.add(full_path.relative_to(base_dir))

    # Apply prune rules
    def is_pruned(path):
        parts = Path(path).parts
        return any(prune in parts for prune in prune_dirs)

    return [str(f) for f in files if not is_pruned(f)]

def create_zip(files, zip_name='addon.zip'):
    base_dir = Path(__file__).parent
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in files:
            full_path = base_dir / file
            if full_path.exists():
                zipf.write(full_path, os.path.join("screensaver.immich.slideshow", file))
                print(f"Added: {file}")
    print(f"Created {zip_name}")

if __name__ == '__main__':
    files = get_manifest_files()
    create_zip(files)