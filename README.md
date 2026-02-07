# dangerouslaser Kodi Repository

Kodi addon repository hosted on GitHub Pages. Automatically updated when addons release new versions.

## Installing in Kodi

1. Download the latest `repository.dangerouslaser-x.x.x.zip` from [Releases](https://github.com/dangerouslaser/repository.dangerouslaser/releases)
2. In Kodi: **Settings > Add-ons > Install from zip file**
3. Select the downloaded zip
4. The repository is now installed - browse addons via **Install from repository > dangerouslaser Repository**

## Available Addons

| Addon | Description |
|-------|-------------|
| [Verse](https://github.com/dangerouslaser/verse) | Modern web interface for Kodi |

## For Addon Developers

### Adding an addon to this repository

1. Add an entry to `addons.json`:
   ```json
   {
     "repo": "dangerouslaser/your-addon",
     "addon_id": "plugin.your.addon",
     "asset_pattern": "plugin.your.addon-*.zip"
   }
   ```

2. Add the dispatch workflow to your addon repo (see below).

### Triggering a repository update from your addon

Add this to your addon's release workflow:

```yaml
- name: Update Kodi repository
  run: |
    gh api repos/dangerouslaser/repository.dangerouslaser/dispatches \
      -f event_type=addon-released
  env:
    GH_TOKEN: ${{ secrets.REPO_DISPATCH_TOKEN }}
```

### Local development

```bash
# Generate repository locally (requires gh CLI)
python generate_repo.py

# Output is in dist/
```
