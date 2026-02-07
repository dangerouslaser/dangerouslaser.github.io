#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ADDONS_JSON="$SCRIPT_DIR/addons.json"

if [ $# -ne 1 ]; then
  echo "Usage: $0 <path-to-addon-repo>"
  exit 1
fi

ADDON_DIR="$(cd "$1" && pwd)"

# Find addon.xml
ADDON_XML=""
for candidate in "$ADDON_DIR/addon.xml" "$ADDON_DIR"/*/addon.xml; do
  if [ -f "$candidate" ]; then
    ADDON_XML="$candidate"
    break
  fi
done

if [ -z "$ADDON_XML" ]; then
  echo "Error: No addon.xml found in $ADDON_DIR"
  exit 1
fi

# Extract addon_id from addon.xml
ADDON_ID=$(python3 -c "
from xml.etree import ElementTree as ET
tree = ET.parse('$ADDON_XML')
print(tree.getroot().get('id', ''))
")
if [ -z "$ADDON_ID" ]; then
  echo "Error: Could not parse addon id from $ADDON_XML"
  exit 1
fi

# Get GitHub repo from git remote
GITHUB_REPO=$(git -C "$ADDON_DIR" remote get-url origin 2>/dev/null | sed -E 's|.*github\.com[:/]||;s|\.git$||')
if [ -z "$GITHUB_REPO" ]; then
  echo "Error: Could not determine GitHub repo from git remote in $ADDON_DIR"
  exit 1
fi

ASSET_PATTERN="${ADDON_ID}-*.zip"

echo "Addon ID:      $ADDON_ID"
echo "GitHub repo:   $GITHUB_REPO"
echo "Asset pattern: $ASSET_PATTERN"
echo ""

# Check if already in addons.json
if grep -q "\"$ADDON_ID\"" "$ADDONS_JSON"; then
  echo "Already in addons.json, skipping."
else
  # Add entry to addons.json
  python3 -c "
import json, sys
with open('$ADDONS_JSON') as f:
    config = json.load(f)
config['addons'].append({
    'repo': '$GITHUB_REPO',
    'addon_id': '$ADDON_ID',
    'asset_pattern': '$ASSET_PATTERN'
})
with open('$ADDONS_JSON', 'w') as f:
    json.dump(config, f, indent=2)
    f.write('\n')
"
  echo "Added to addons.json"
fi

# Create dispatch workflow in the addon repo
WORKFLOW_DIR="$ADDON_DIR/.github/workflows"
WORKFLOW_FILE="$WORKFLOW_DIR/update-kodi-repo.yml"

if [ -f "$WORKFLOW_FILE" ]; then
  echo "Workflow already exists at $WORKFLOW_FILE, skipping."
else
  mkdir -p "$WORKFLOW_DIR"
  cat > "$WORKFLOW_FILE" << 'WORKFLOW'
name: Update Kodi Repository

on:
  release:
    types: [published]

jobs:
  notify-repo:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger repository update
        run: |
          gh api repos/dangerouslaser/dangerouslaser.github.io/dispatches \
            -f event_type=addon-released
        env:
          GH_TOKEN: ${{ secrets.REPO_DISPATCH_TOKEN }}
WORKFLOW
  echo "Created $WORKFLOW_FILE"
fi

echo ""
echo "Done! Next steps:"
echo "  1. Add REPO_DISPATCH_TOKEN secret to $GITHUB_REPO (GitHub PAT with repo scope)"
echo "  2. Commit and push the workflow in $ADDON_DIR"
echo "  3. Commit and push addons.json in $SCRIPT_DIR"
