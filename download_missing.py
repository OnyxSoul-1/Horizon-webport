import os
import requests
from concurrent.futures import ThreadPoolExecutor

# ==========================================
# CONFIGURATION
# ==========================================
BASE_URL = "https://incariclient.org/horizon-26-3-beta/fs/res/"
MANIFEST_FILE = "manifest.txt"

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
def download_file(file_path):
    # Skip files we already have
    if any(existing in file_path for existing in EXISTING_FILES):
        # print(f"[-] Skipping (already have): {file_path}")
        return True

    # Skip the giant worldgen/biome files if they are in a tarball
    if "worldgen/" in file_path or "biome-parameters/" in file_path:
        if "../" in file_path:
            return True

    url = BASE_URL + file_path
    # Download DIRECTLY into the current workspace directory
    local_path = file_path 
    
    # Create directories
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    
    try:
        print(f"[+] Downloading: {file_path}")
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"[!] Failed: {file_path} - {e}")
        return False

def main():
    if not os.path.exists(MANIFEST_FILE):
        print(f"Error: {MANIFEST_FILE} not found.")
        return

    print("Parsing manifest...")
    files_to_download = []
    
    with open(MANIFEST_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
        
    lines = content.replace('\t', '\n').split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('assets/') or line.startswith('worldgen/') or line.startswith('biome-parameters/'):
            if not line.isdigit():
                files_to_download.append(line)

    print(f"Found {len(files_to_download)} files in manifest.")
    print("Starting download (skipping existing files)...")

    with ThreadPoolExecutor(max_workers=10) as executor:
        for file_path in files_to_download:
            executor.submit(download_file, file_path)

    print("Download complete. Files are saved directly in the workspace.")

if __name__ == "__main__":
    main()
