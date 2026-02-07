#!/usr/bin/env python3
"""
Kodi Repository Generator

Fetches latest releases from configured GitHub addon repos,
downloads release zips, and generates addons.xml + addons.xml.md5.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = SCRIPT_DIR / "addons.json"
OUTPUT_DIR = SCRIPT_DIR / "dist"


def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)


def fetch_latest_release(repo):
    """Use gh CLI to get the latest release info."""
    result = subprocess.run(
        ["gh", "release", "view", "--repo", repo, "--json", "tagName,assets"],
        capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)


def download_asset(repo, tag, pattern, dest_dir):
    """Download a release asset matching the pattern."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["gh", "release", "download", tag, "--repo", repo,
         "--pattern", pattern, "--dir", str(dest_dir), "--clobber"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    # Find the downloaded file
    for f in dest_dir.iterdir():
        if f.suffix == ".zip":
            return f
    return None


def extract_addon_xml(zip_path, addon_id):
    """Extract addon.xml from an addon zip file."""
    with zipfile.ZipFile(zip_path) as zf:
        # Look for addon.xml in the root of the zip or in addon_id/
        for name in zf.namelist():
            basename = os.path.basename(name)
            dirname = os.path.dirname(name).rstrip("/")
            if basename == "addon.xml" and (dirname == "" or dirname == addon_id):
                return zf.read(name).decode("utf-8")
    return None


def md5sum(filepath):
    """Calculate MD5 checksum of a file."""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def md5_string(content):
    """Calculate MD5 of a string."""
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def generate_addons_xml(addon_xmls):
    """Generate the master addons.xml from a list of addon.xml contents."""
    parts = ['<?xml version="1.0" encoding="UTF-8"?>\n<addons>']

    for xml_content in addon_xmls:
        # Strip XML declaration if present
        lines = xml_content.strip().splitlines()
        filtered = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("<?xml"):
                continue
            filtered.append(line)
        parts.append("\n".join(filtered))

    parts.append("</addons>\n")
    return "\n".join(parts)


def main():
    config = load_config()

    # Clean and prepare output directory
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    addon_xmls = []

    # Process the repository addon itself
    repo_addon_dir = SCRIPT_DIR / "repository.dangerouslaser"
    repo_addon_xml_path = repo_addon_dir / "addon.xml"
    if repo_addon_xml_path.exists():
        # Read version from addon.xml
        tree = ET.parse(repo_addon_xml_path)
        root = tree.getroot()
        version = root.get("version", "1.0.0")
        addon_id = root.get("id", "repository.dangerouslaser")

        # Create the repository addon zip
        dest_dir = OUTPUT_DIR / addon_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        zip_name = f"{addon_id}-{version}.zip"
        zip_path = dest_dir / zip_name

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in repo_addon_dir.iterdir():
                zf.write(f, f"{addon_id}/{f.name}")

        # Also create a zip at root level for easy direct download
        shutil.copy2(zip_path, OUTPUT_DIR / zip_name)

        # Add addon.xml content
        addon_xmls.append(repo_addon_xml_path.read_text("utf-8"))

        # Generate MD5 for the zip
        with open(str(zip_path) + ".md5", "w") as f:
            f.write(md5sum(zip_path))

        print(f"  [repo] {addon_id} v{version}")

    # Process each configured addon
    for addon in config["addons"]:
        repo = addon["repo"]
        addon_id = addon["addon_id"]
        pattern = addon["asset_pattern"]

        print(f"  Fetching latest release from {repo}...")

        try:
            release = fetch_latest_release(repo)
        except subprocess.CalledProcessError as e:
            print(f"  WARNING: Could not fetch release for {repo}: {e.stderr}")
            continue

        tag = release["tagName"]
        print(f"  Found {tag}")

        # Download the release asset
        addon_dest = OUTPUT_DIR / addon_id
        zip_path = download_asset(repo, tag, pattern, addon_dest)

        if not zip_path:
            print(f"  WARNING: No zip found matching '{pattern}' in {repo} {tag}")
            continue

        # Extract addon.xml from the zip
        xml_content = extract_addon_xml(zip_path, addon_id)
        if not xml_content:
            print(f"  WARNING: No addon.xml found in {zip_path.name}")
            continue

        addon_xmls.append(xml_content)

        # Generate MD5 for the zip
        with open(str(zip_path) + ".md5", "w") as f:
            f.write(md5sum(zip_path))

        print(f"  {addon_id} {tag} -> {zip_path.name}")

    if not addon_xmls:
        print("ERROR: No addons found!")
        sys.exit(1)

    # Generate addons.xml
    addons_xml = generate_addons_xml(addon_xmls)
    addons_xml_path = OUTPUT_DIR / "addons.xml"
    addons_xml_path.write_text(addons_xml, "utf-8")

    # Generate addons.xml.md5
    addons_md5_path = OUTPUT_DIR / "addons.xml.md5"
    addons_md5_path.write_text(md5_string(addons_xml))

    # Generate directory index pages for Kodi's HTTP file browser
    generate_index_pages(OUTPUT_DIR)

    print(f"\nRepository generated in {OUTPUT_DIR}/")
    print(f"  addons.xml ({len(addon_xmls)} addons)")
    print(f"  addons.xml.md5")
    print(f"  index.html (directory listings)")


def generate_index_pages(root_dir):
    """Generate index.html files that mimic directory listings for Kodi."""
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirpath = Path(dirpath)
        is_root = dirpath == root_dir
        entries = []

        if not is_root:
            # Subdirectories only in addon folders
            for d in sorted(dirnames):
                entries.append(f'<a href="{d}/">{d}/</a>')

        # Add files - at root level only show zips (for Kodi's "Install from zip" browser)
        for f in sorted(filenames):
            if f == "index.html":
                continue
            if is_root and not f.endswith(".zip"):
                continue
            entries.append(f'<a href="{f}">{f}</a>')

        links = "\n".join(entries)
        html = f'<html><body>\n{links}\n</body></html>\n'
        (dirpath / "index.html").write_text(html, "utf-8")


if __name__ == "__main__":
    print("Generating Kodi repository...\n")
    main()
