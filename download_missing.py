import os
import shutil
import tarfile
import tempfile
import requests
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

# ==========================================
# CONFIGURATION
# ==========================================
BASE_URL = "https://incariclient.org/horizon-26-3-beta/fs/res/"
MANIFEST_FILE = "manifest.txt"
RESOURCE_ROOT = os.path.join("fs", "res")

# Files you ALREADY have. The script will skip these.
EXISTING_FILES = [
    "snippets/horizon-os-37ecb54e3...",
    "snippets/horizon-os-37ecb54e3.../h",
    "snippets/horizon-os-37ecb54e3.../inline0.js",
    "snippets/horizon-os-37ecb54e3.../inline1.js",
    "snippets/horizon-os-37ecb54e3.../inline2.js",
    "snippets/horizon-os-37ecb54e3.../inline3.js",
    "boot.tar.gz",
    "horizon-client.js",
    "horizon-client_bg.wasm.part1",
    "horizon-client_bg.wasm.part2",
    "horizon-client_bg.wasm.part3",
    "horizon-client_bg.wasm.part4",
    "README.md",
    "audio.js",
    "banner.webp",
    "build.json",
    "index.html",
    "main.js",
    "manifest.txt",
    "sw.js",
    "vce701823e78c4301a35b7e07294...",
    "worker.js"
]

# ==========================================
# DOWNLOAD LOGIC
# ==========================================
def download_file(file_path, expected_size):
    local_path = os.path.join(RESOURCE_ROOT, file_path)

    if os.path.isfile(local_path) and os.path.getsize(local_path) == expected_size:
        return True

    # Skip files we already have
    if any(existing in file_path for existing in EXISTING_FILES):
        # print(f"[-] Skipping (already have): {file_path}")
        return True

    # Skip the giant worldgen/biome files if they are in a tarball
    if "worldgen/" in file_path or "biome-parameters/" in file_path:
        if "../" in file_path:
            return True

    url = BASE_URL + file_path
    partial_path = local_path + ".part"
    
    # Create directories
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    
    try:
        print(f"[+] Downloading: {file_path}")
        with requests.get(url, stream=True, timeout=30) as response:
            response.raise_for_status()
            with open(partial_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        if os.path.getsize(partial_path) != expected_size:
            raise ValueError(f"expected {expected_size} bytes, got {os.path.getsize(partial_path)}")
        os.replace(partial_path, local_path)
        return True
    except Exception as e:
        print(f"[!] Failed: {file_path} - {e}")
        if os.path.exists(partial_path):
            os.remove(partial_path)
        return False

def parse_manifest(content):
    files_to_download = []
    bundles = {}

    for line in content.splitlines():
        fields = line.split()
        if len(fields) < 2:
            continue

        file_path = fields[0]
        if not file_path.startswith(("assets/", "worldgen/", "biome-parameters/")):
            continue

        expected_size = int(fields[1])
        bundle = fields[2] if len(fields) > 2 and fields[2].startswith("../") else None
        if bundle:
            bundles.setdefault(bundle, []).append((file_path, expected_size))
        else:
            files_to_download.append((file_path, expected_size))

    return files_to_download, bundles

def extract_bundle(bundle_path, files):
    url = urljoin(BASE_URL, bundle_path)
    print(f"[+] Downloading bundle: {url}")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, "resources.tar.gz")
            with requests.get(url, stream=True, timeout=30) as response:
                response.raise_for_status()
                with open(archive_path, "wb") as archive_file:
                    for chunk in response.iter_content(chunk_size=8192):
                        archive_file.write(chunk)

            root = os.path.realpath(RESOURCE_ROOT)
            with tarfile.open(archive_path, "r:gz") as archive:
                members = archive.getmembers()
                for member in members:
                    relative_path = os.path.normpath(member.name)
                    target_path = os.path.realpath(os.path.join(root, relative_path))
                    if (relative_path in ("", ".") or os.path.isabs(relative_path)
                            or os.path.commonpath((root, target_path)) != root):
                        if relative_path in ("", "."):
                            continue
                        raise ValueError(f"unsafe archive path: {member.name}")
                    if not (member.isdir() or member.isfile()):
                        raise ValueError(f"unsupported archive entry: {member.name}")

                for member in members:
                    relative_path = os.path.normpath(member.name)
                    if relative_path in ("", "."):
                        continue
                    target_path = os.path.join(root, relative_path)
                    if member.isdir():
                        os.makedirs(target_path, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        source = archive.extractfile(member)
                        if source is None:
                            raise ValueError(f"could not read archive entry: {member.name}")
                        with source, open(target_path, "wb") as target:
                            shutil.copyfileobj(source, target)

        incomplete = [path for path, size in files
                      if not os.path.isfile(os.path.join(root, path))
                      or os.path.getsize(os.path.join(root, path)) != size]
        if incomplete:
            raise ValueError(f"bundle is missing {len(incomplete)} manifest files")
        return True
    except Exception as e:
        print(f"[!] Failed bundle: {bundle_path} - {e}")
        return False

def main():
    if not os.path.exists(MANIFEST_FILE):
        print(f"Error: {MANIFEST_FILE} not found.")
        return

    print("Parsing manifest...")
    files_to_download = []
    
    with open(MANIFEST_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
        
    files_to_download, bundles = parse_manifest(content)

    print(f"Found {len(files_to_download)} loose files and {sum(map(len, bundles.values()))} bundled files in manifest.")
    print("Starting download (skipping existing files)...")

    failures = 0
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(lambda entry: download_file(*entry), files_to_download)
        failures += sum(not result for result in results)

    for bundle_path, files in bundles.items():
        if not extract_bundle(bundle_path, files):
            failures += 1

    if failures:
        print(f"Download finished with {failures} failures.")
        return 1

    print(f"Download complete. Files are saved under {RESOURCE_ROOT}/.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
