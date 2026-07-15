#!/usr/bin/env python3
"""mcp-dashboard — inspect and edit per-project MCP server config of Claude Code.

Subcommands:
  build  — parse ~/.claude.json (+ per-project .mcp.json / .claude/settings*.json),
           render a single-file HTML dashboard, print its absolute path.
  apply  — read a "=== MCP CHANGES ===" block (produced by the dashboard page)
           from a file, back up ~/.claude.json and apply the changes.

Stdlib only. Works on macOS / Windows / Linux, Python 3.9+.
Secrets (env values, headers, key-looking tokens in args/URLs) never reach the HTML.
"""

import argparse
import datetime
import json
import os
import re
import shutil
import sys
import tempfile

# CLAUDE_CONFIG_DIR relocates ~/.claude.json (same rule Claude Code itself uses)
CLAUDE_JSON = os.path.join(
    os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~"), ".claude.json")
SECRETISH_FLAG = re.compile(r"(key|token|secret|pass|auth|bearer|credential)", re.I)
SECRETISH_VALUE = re.compile(r"^[A-Za-z0-9_\-\.=+/]{20,}$")
MASK = "•••"  # •••


# ---------------------------------------------------------------- helpers

def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def home_short(path):
    home = os.path.expanduser("~")
    if path == home:
        return "~"
    if path.startswith(home + os.sep) or path.startswith(home + "/"):
        return "~" + path[len(home):]
    return path


def redact_url(url):
    """Keep scheme+host+path, mask query values and token-looking path segments."""
    m = re.match(r"^(\w+://[^/?#]+)([^?#]*)(\?.*)?$", url or "")
    if not m:
        return url
    base, path, query = m.group(1), m.group(2) or "", m.group(3)
    segs = []
    for seg in path.split("/"):
        segs.append(MASK if SECRETISH_VALUE.match(seg) else seg)
    out = base + "/".join(segs)
    if query:
        out += "?" + MASK
    return out


def redact_args(args):
    out, prev_flag_secret = [], False
    for a in args or []:
        if prev_flag_secret or SECRETISH_VALUE.match(a):
            out.append(MASK)
        elif "=" in a and SECRETISH_FLAG.search(a.split("=", 1)[0]):
            out.append(a.split("=", 1)[0] + "=" + MASK)
        else:
            out.append(a)
        prev_flag_secret = a.startswith("-") and bool(SECRETISH_FLAG.search(a))
    return out


def describe_server(defn):
    """(transport, redacted detail, env key names) — never leaks values."""
    defn = defn or {}
    if defn.get("command"):
        detail = " ".join([defn["command"]] + redact_args(defn.get("args")))
        return "stdio", detail, sorted((defn.get("env") or {}).keys())
    transport = defn.get("transport") or defn.get("type") or "http"
    url = redact_url(defn.get("url", ""))
    keys = sorted((defn.get("headers") or {}).keys())
    return transport, url, keys


# ---------------------------------------------------------------- build

def load_project_settings(path):
    """Merge .mcp.json approval keys from .claude/settings.json + settings.local.json."""
    merged = {}
    for name in ("settings.json", "settings.local.json"):
        data = read_json(os.path.join(path, ".claude", name)) or {}
        for key in ("enabledMcpjsonServers", "disabledMcpjsonServers",
                    "enableAllProjectMcpServers"):
            if key in data:
                merged[key] = data[key]
    return merged


def mcpjson_state(name, entry, settings):
    """State of a .mcp.json server: 'on' | 'off' | 'ask' (not yet approved)."""
    def get(key, default):
        if key in settings:
            return settings[key]
        return entry.get(key, default)

    if name in get("disabledMcpjsonServers", []):
        return "off"
    if name in get("enabledMcpjsonServers", []) or get("enableAllProjectMcpServers", False):
        return "on"
    return "ask"


def collect(include_missing=False):
    config = read_json(CLAUDE_JSON)
    if config is None:
        sys.exit("ERROR: cannot read %s — is Claude Code installed?" % CLAUDE_JSON)

    raw_projects = config.get("projects") or {}
    projects = []
    for path in sorted(raw_projects):
        exists = os.path.isdir(path)
        if exists or include_missing:
            projects.append({"path": path, "name": home_short(path), "exists": exists})
    ppaths = [p["path"] for p in projects]

    servers = {}   # name -> row
    states = {}    # name -> {path: state}

    def row(name, group, defn=None, defined_in=None):
        transport, detail, keys = describe_server(defn) if defn else ("", "", [])
        r = servers.setdefault(name, {
            "name": name, "group": group, "transport": transport,
            "detail": detail, "envKeys": keys, "definedIn": []})
        if defined_in and defined_in not in r["definedIn"]:
            r["definedIn"].append(defined_in)
        return r

    for name, defn in (config.get("mcpServers") or {}).items():
        row(name, "global", defn)

    mcpjson_names = {}   # path -> set of .mcp.json server names (needed by `apply` too)
    for p in projects:
        path, entry = p["path"], raw_projects[p["path"]]
        for name, defn in (entry.get("mcpServers") or {}).items():
            row(name, "local", defn, defined_in=path)
        project_mcpjson = (read_json(os.path.join(path, ".mcp.json")) or {}).get("mcpServers") or {}
        mcpjson_names[path] = set(project_mcpjson)
        settings = load_project_settings(path)
        for name, defn in project_mcpjson.items():
            row(name, "mcpjson", defn, defined_in=path)
            states.setdefault(name, {})[path] = mcpjson_state(name, entry, settings)
        for name in entry.get("disabledMcpServers") or []:
            if name not in servers:
                row(name, "dynamic")

    for name, r in servers.items():
        st = states.setdefault(name, {})
        for p in projects:
            path, entry = p["path"], raw_projects[p["path"]]
            if path in st:
                continue
            disabled = name in (entry.get("disabledMcpServers") or [])
            if r["group"] in ("global", "dynamic"):
                st[path] = "off" if disabled else "on"
            elif r["group"] == "local":
                st[path] = ("off" if disabled else "on") if path in r["definedIn"] else "na"
            else:  # mcpjson server, project without that .mcp.json entry
                st[path] = "na"

    order = {"global": 0, "dynamic": 1, "local": 2, "mcpjson": 3}
    rows = sorted(servers.values(), key=lambda r: (order[r["group"]], r["name"].lower()))
    return {
        "generatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "projects": projects,
        "servers": rows,
        "states": states,
    }, mcpjson_names


def cmd_build(args):
    data, _ = collect(include_missing=args.include_missing)
    template = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "assets", "dashboard.html")
    with open(template, "r", encoding="utf-8") as f:
        html = f.read()
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = html.replace("/*__MCP_DATA__*/null", payload)
    out_dir = args.out or tempfile.mkdtemp(prefix="mcp-dashboard-")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "mcp-dashboard.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(os.path.abspath(out))


# ---------------------------------------------------------------- apply

def parse_changes(text):
    """Parse the block the dashboard's Copy button produces.

    === MCP CHANGES ===
    project: /abs/path
    enable: a, b
    disable: c
    === END ===
    """
    changes, current = [], None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("==="):
            continue
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "project":
            current = {"project": value, "enable": [], "disable": []}
            changes.append(current)
        elif key in ("enable", "disable") and current is not None:
            current[key] += [n.strip() for n in value.split(",") if n.strip()]
        else:
            sys.exit("ERROR: unrecognized line in changes block: %r" % line)
    return [c for c in changes if c["enable"] or c["disable"]]


def cmd_apply(args):
    with open(args.changes_file, "r", encoding="utf-8") as f:
        changes = parse_changes(f.read())
    if not changes:
        sys.exit("Nothing to apply: the block contains no enable/disable lines.")

    config = read_json(CLAUDE_JSON)
    if config is None:
        sys.exit("ERROR: cannot read %s" % CLAUDE_JSON)
    raw_projects = config.get("projects") or {}
    _, mcpjson_names = collect(include_missing=True)

    log = []
    for change in changes:
        path = change["project"]
        entry = raw_projects.get(path)
        if entry is None:
            sys.exit("ERROR: project %r not found in ~/.claude.json — "
                     "re-run `build` and copy a fresh block." % path)
        in_mcpjson = mcpjson_names.get(path, set())
        for action in ("enable", "disable"):
            for name in change[action]:
                if name in in_mcpjson:
                    en = entry.setdefault("enabledMcpjsonServers", [])
                    dis = entry.setdefault("disabledMcpjsonServers", [])
                    (dis if action == "enable" else en)[:] = \
                        [n for n in (dis if action == "enable" else en) if n != name]
                    target = en if action == "enable" else dis
                    if name not in target:
                        target.append(name)
                else:
                    dis = entry.setdefault("disabledMcpServers", [])
                    if action == "disable" and name not in dis:
                        dis.append(name)
                    elif action == "enable":
                        dis[:] = [n for n in dis if n != name]
                log.append("%s %s in %s" % (action, name, home_short(path)))

    if args.dry_run:
        print("DRY RUN — nothing written. Would apply:")
        print("\n".join("  " + l for l in log))
        return

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = CLAUDE_JSON + ".bak-mcpdash-" + stamp
    shutil.copy2(CLAUDE_JSON, backup)

    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(CLAUDE_JSON), prefix=".claude.json.")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CLAUDE_JSON)

    print("Applied %d change(s):" % len(log))
    print("\n".join("  " + l for l in log))
    print("Backup: %s" % backup)
    print("NOTE: changes take effect in NEW Claude Code sessions; other sessions "
          "running right now may overwrite them — re-run `build` to verify.")


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="render the HTML dashboard, print its path")
    b.add_argument("--out", help="output directory (default: fresh temp dir)")
    b.add_argument("--include-missing", action="store_true",
                   help="also list projects whose directory no longer exists")
    b.set_defaults(func=cmd_build)
    a = sub.add_parser("apply", help="apply a pasted MCP CHANGES block")
    a.add_argument("changes_file", help="file containing the pasted block")
    a.add_argument("--dry-run", action="store_true", help="print, don't write")
    a.set_defaults(func=cmd_apply)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
