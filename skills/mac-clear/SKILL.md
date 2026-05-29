---
name: mac-clear
description: "..."
---

<!-- hidden: Clean up Mac from junk, caches, unused apps, and reclaim disk space. -->

# Mac Cleanup

Scan the Mac for space-wasting junk and help the user reclaim disk space. Work interactively — show findings, ask what to delete, execute cleanup.

## Step 1: Overview

Run `df -h /` to show current free space, then scan all major consumers:

```bash
# Top-level user dirs
du -sh ~/*/  | sort -rh | head -15

# Library subdirs
du -sh ~/Library/Application\ Support/*/ | sort -rh | head -15
du -sh ~/Library/Caches/*/ | sort -rh | head -10
du -sh ~/Library/Containers/*/ | sort -rh | head -10
du -sh ~/Library/Group\ Containers/*/ | sort -rh | head -5
du -sh ~/Library/Developer/*/ | sort -rh | head -5

# System-level
du -sh /Library/Developer/*/ | sort -rh | head -5
```

Present a summary table with sizes and recommendations.

## Step 2: Safe auto-cleanup targets

These are always safe to clean (ask user before deleting):

### Caches (~/Library/Caches/)

- Safe to delete entirely: `rm -rf ~/Library/Caches/*`
- Apps will recreate caches on next launch
- Typical savings: 3-8 GB

### Old installers in Downloads

- `~/Downloads/*.dmg`, `*.apk`, `*.pkg` — installers already used
- `~/Downloads/*.mp4` — random downloaded videos
- Zoom recordings in `~/Downloads/zoom recordings/`
- Soulseek downloads in `~/Downloads/soulseek/`

### Build artifacts and dev caches

- `node_modules/` in project dirs — `find <dir> -maxdepth 3 -name "node_modules" -type d -exec rm -rf {} +`
- `.venv/`, `venv/` in Python projects — same pattern
- `__pycache__/`, `.idea/` — same pattern
- Rust `target/` dirs (e.g. Tauri builds) — can be huge (5-10 GB each)
- `~/Library/pnpm/` — pnpm package cache
- `~/Library/Caches/pip/` — pip cache
- `~/Library/Caches/Homebrew/` — brew cache

### Docker

- `docker system prune -a --volumes -f` — removes unused containers, images, volumes
- Check `~/Library/Containers/com.docker.docker/` size

### Xcode / Developer tools

- `~/Library/Developer/CoreSimulator/` — user simulators, clean with `xcrun simctl delete all` + `xcrun simctl runtime delete all`
- `/Library/Developer/CoreSimulator/` — system simulators, SIP-protected. If full Xcode installed — huge. Remove Xcode if not needed: `sudo rm -rf /Applications/Xcode.app`
- If Xcode not needed, only Command Line Tools are required for git/python3

## Step 3: Interactive cleanup targets

Ask the user about these before touching:

### Large app data

- **Claude Desktop** `~/Library/Application Support/Claude/vm_bundles/` — Computer Use VM, 10+ GB if not used
- **Telegram** `~/Library/Group Containers/*keepcoder.Telegram/` — message DB grows over time, can't clean without re-login
- **Chrome** `~/Library/Application Support/Google/Chrome/` — profile data, caches
- **Cursor** `~/Library/Application Support/Cursor/logs/`, `CachedData/`, `WebStorage/` — safe to clean
- **Steam** `~/Library/Application Support/Steam/` — games, delete if not playing
- **Apple Music** `~/Apple Music/` — may contain DRM-protected .m4p files (useless without subscription) and old downloads

### Project directories

- Old project dirs (PycharmProjects, cursor projects, etc.) — check if still needed
- Within active projects, clean build artifacts only

### System data (157+ GB "System Data" in macOS settings)

- Mostly purgeable space — macOS auto-frees when needed
- Time Machine local snapshots: `tmutil listlocalsnapshots /`
- Delete snapshots: `tmutil deletelocalsnapshots <date>`
- `/private/var/vm/` — swap, don't touch
- `/private/var/folders/` — system temp, don't touch

## Rules

1. **Always show current free space** before and after cleanup
2. **Always ask before deleting** — show what will be deleted and size
3. **Never delete .env files, credentials, SSH keys**
4. **Never delete active project source code** — only build artifacts
5. **Group deletions by risk level** — safe caches first, then ask about everything else
6. **Explain what each thing is** when the user asks
7. **After cleanup, show total space reclaimed**
