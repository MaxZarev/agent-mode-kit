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
from urllib.parse import urlsplit, urlunsplit

# CLAUDE_CONFIG_DIR relocates ~/.claude.json (same rule Claude Code itself uses)
CLAUDE_JSON = os.path.join(
    os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~"), ".claude.json")
# Skill's own persistent state: hidden projects + known projects (for "new" detection)
STATE_FILE = os.path.join(
    os.environ.get("CLAUDE_CONFIG_DIR")
    or os.path.join(os.path.expanduser("~"), ".claude"), "mcp-dashboard.json")
SECRETISH_FLAG = re.compile(r"(key|token|secret|pass|auth|bearer|credential)", re.I)
SECRETISH_VALUE = re.compile(r"^[A-Za-z0-9_\-\.=+/]{20,}$")
PATHISH = re.compile(r"^([/~.]|[A-Za-z]:[\\/])")  # filesystem paths are not secrets
URLISH = re.compile(r"^\w+://")
MASK = "•••"  # •••
# claude.ai connectors ("claude.ai Gmail", …) — the Claude Desktop app pulls
# them straight from the account and ignores per-project config entirely
CONNECTOR_PREFIX = "claude.ai "
# plugin-provided servers ("plugin:name@marketplace") — defined by the plugin, not here
PLUGIN_PREFIX = "plugin:"
# servers built into Claude Code itself — no definition anywhere in the config,
# yet per-project disabling via disabledMcpServers is perfectly legitimate
BUILTIN_SERVERS = {"claude-in-chrome", "ide"}


# ---------------------------------------------------------------- helpers

def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def load_state():
    return read_json(STATE_FILE) or {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(STATE_FILE), prefix=".mcp-dashboard.")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


def home_short(path):
    home = os.path.expanduser("~")
    if path == home:
        return "~"
    if path.startswith(home + os.sep) or path.startswith(home + "/"):
        return "~" + path[len(home):]
    return path


def redact_url(url):
    """Keep scheme+host+path; mask userinfo, query, fragment and token-looking
    path segments — credentials can hide in any of those."""
    try:
        parts = urlsplit(url or "")
    except ValueError:
        return MASK
    if not parts.scheme or not parts.netloc:
        return url
    netloc = parts.netloc
    if "@" in netloc:
        netloc = MASK + "@" + netloc.rsplit("@", 1)[1]
    path = "/".join(MASK if SECRETISH_VALUE.match(seg) else seg
                    for seg in parts.path.split("/"))
    return urlunsplit((parts.scheme, netloc, path,
                       MASK if parts.query else "",
                       MASK if parts.fragment else ""))


def redact_args(args):
    out, prev_flag_secret = [], False
    for a in args or []:
        a = str(a)
        if prev_flag_secret:
            out.append(MASK)
        elif URLISH.match(a):
            out.append(redact_url(a))
        elif SECRETISH_VALUE.match(a) and not PATHISH.match(a):
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

def load_denied_servers():
    """User-scope deniedMcpServers from settings.json / settings.local.json —
    globally blocked servers (entries are {"serverName": X} objects or strings)."""
    base = (os.environ.get("CLAUDE_CONFIG_DIR")
            or os.path.join(os.path.expanduser("~"), ".claude"))
    denied = set()
    for fname in ("settings.json", "settings.local.json"):
        for item in (read_json(os.path.join(base, fname)) or {}).get("deniedMcpServers") or []:
            name = item.get("serverName") if isinstance(item, dict) else item
            if name:
                denied.add(name)
    return denied


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
    """State of a .mcp.json server: 'on' | 'off' | 'ask' (not yet approved).

    enabled/disabled lists may also be the string "all"; disabled wins over enabled.
    """
    def get(key, default):
        if key in settings:
            return settings[key]
        return entry.get(key, default)

    def has(value, name):
        return value == "all" or (isinstance(value, list) and name in value)

    if has(get("disabledMcpjsonServers", []), name):
        return "off"
    if has(get("enabledMcpjsonServers", []), name) or get("enableAllProjectMcpServers", False):
        return "on"
    return "ask"


def dynamic_group(name):
    """Group for a name that exists only in disable lists. claude.ai connectors,
    plugin servers and Claude Code's built-in servers legitimately have no
    definition in ~/.claude.json — anything else found there is a stale
    leftover of a removed server."""
    if name.startswith(CONNECTOR_PREFIX):
        return "connector"
    if name.startswith(PLUGIN_PREFIX):
        return "plugin"
    if name in BUILTIN_SERVERS:
        return "builtin"
    return None


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

    servers = {}   # name -> column descriptor
    states = {}    # name -> {path: state}

    def row(name, group, defn=None, defined_in=None):
        transport, detail, keys = describe_server(defn) if defn else ("", "", [])
        r = servers.setdefault(name, {
            "name": name, "group": group, "transport": transport,
            "detail": detail, "envKeys": keys, "definedIn": []})
        if defined_in and defined_in not in r["definedIn"]:
            r["definedIn"].append(defined_in)
        return r

    # 1. Servers with a real definition: user scope, local scope, repo .mcp.json.
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

    # 2. Names that live only in disable/approval lists. Connectors and plugin
    #    servers are real despite having no definition here; every other such
    #    name is a "ghost" — a leftover of a server that was since removed.
    #    Ghosts go to a cleanup list instead of masquerading as servers.
    ghost_hits = {}   # name -> {path: [config keys the name lingers in]}

    def ghost(name, path, source):
        ghost_hits.setdefault(name, {}).setdefault(path, []).append(source)

    for p in projects:
        path, entry = p["path"], raw_projects[p["path"]]
        for name in entry.get("disabledMcpServers") or []:
            if name in servers:
                continue
            group = dynamic_group(name)
            if group:
                row(name, group)
            else:
                ghost(name, path, "disabledMcpServers")
    for p in projects:
        path, entry = p["path"], raw_projects[p["path"]]
        for key in ("enabledMcpjsonServers", "disabledMcpjsonServers"):
            lst = entry.get(key)
            if not isinstance(lst, list):
                continue
            for name in lst:
                if name not in servers and name not in mcpjson_names[path]:
                    ghost(name, path, key)

    denied = load_denied_servers()
    for name in sorted(denied):
        if name not in servers and dynamic_group(name):
            row(name, dynamic_group(name))

    for name, r in servers.items():
        st = states.setdefault(name, {})
        for p in projects:
            path, entry = p["path"], raw_projects[p["path"]]
            if name in denied:  # blocked in user settings — overrides everything
                st[path] = "blk"
                continue
            if path in st:
                continue
            disabled = name in (entry.get("disabledMcpServers") or [])
            if r["group"] in ("global", "builtin", "connector", "plugin"):
                st[path] = "off" if disabled else "on"
            elif r["group"] == "local":
                st[path] = ("off" if disabled else "on") if path in r["definedIn"] else "na"
            else:  # mcpjson server, project without that .mcp.json entry
                st[path] = "na"

    ghost_names = set(ghost_hits)
    ghost_names.update(n for n in denied
                       if n not in servers and dynamic_group(n) is None)
    ghosts = []
    for name in sorted(ghost_names, key=str.lower):
        hits = ghost_hits.get(name, {})
        ghosts.append({
            "name": name, "denied": name in denied,
            "projects": [{"path": path, "name": home_short(path),
                          "sources": sorted(set(hits[path]))}
                         for path in sorted(hits)],
        })

    order = {"global": 0, "builtin": 1, "connector": 2, "plugin": 3,
             "local": 4, "mcpjson": 5}
    cols = sorted(servers.values(), key=lambda r: (order[r["group"]], r["name"].lower()))
    return {
        "generatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "projects": projects,
        "servers": cols,
        "states": states,
        "ghosts": ghosts,
    }, mcpjson_names


def cmd_build(args):
    data, _ = collect(include_missing=args.include_missing)
    state = load_state()
    first_run = "knownProjects" not in state
    known = set(state.get("knownProjects") or [])
    hidden = set(state.get("hiddenProjects") or [])
    paths = [p["path"] for p in data["projects"]]
    new = [] if first_run else [p for p in paths if p not in known]
    for p in data["projects"]:
        p["hidden"] = p["path"] in hidden
        p["new"] = p["path"] in new
    state["knownProjects"] = sorted(known | set(paths))
    state["hiddenProjects"] = sorted(hidden)
    save_state(state)
    # default is "desktop" (the safer assumption) until the user picks CLI
    data["uiMode"] = "cli" if state.get("uiMode") == "cli" else "desktop"

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
    if first_run:
        print("FIRST RUN: baseline of %d projects saved — hide the unneeded ones "
              "on the page (the ✕ in a project row), they won't come back."
              % len(paths))
    for p in new:
        print("NEW PROJECT: %s" % p)
    for g in data["ghosts"]:
        where = ", ".join(p["name"] for p in g["projects"])
        note = " (also in deniedMcpServers)" if g["denied"] and where else ""
        if not where:
            where = "~/.claude/settings.json deniedMcpServers"
        print("RUDIMENT: %s — stale config entries in %s%s" % (g["name"], where, note))


# ---------------------------------------------------------------- apply

def parse_changes(text):
    """Parse the block the dashboard's Copy button produces.

    === MCP CHANGES ===
    mode: desktop
    hide: /abs/other-path
    show: /abs/third-path
    project: /abs/path
    enable: a, b
    disable: c
    cleanup: old-ghost
    add: exa
    === END ===

    hide/show are project-VISIBILITY lines (one path each, position-independent);
    mode is the page's "where do you work" switch (cli | desktop). All three go
    to the skill's state file, not to ~/.claude.json. cleanup removes stale
    leftovers of deleted servers from the project's disable/approval lists.
    add connects an existing local-scope server to this project by copying its
    definition from the project where it is already configured.
    """
    changes, current, mode = [], None, None
    visibility = {"hide": [], "show": []}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("==="):
            continue
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "project":
            current = {"project": value, "enable": [], "disable": [],
                       "cleanup": [], "add": []}
            changes.append(current)
        elif key in ("enable", "disable", "cleanup", "add") and current is not None:
            current[key] += [n.strip() for n in value.split(",") if n.strip()]
        elif key in ("hide", "show") and value:
            visibility[key].append(value)
        elif key == "mode":
            if value not in ("cli", "desktop"):
                sys.exit("ERROR: mode must be 'cli' or 'desktop', got %r" % value)
            mode = value
        else:
            sys.exit("ERROR: unrecognized line in changes block: %r" % line)
    return ([c for c in changes
             if c["enable"] or c["disable"] or c["cleanup"] or c["add"]],
            visibility, mode)


def _toggle_mcpjson(entry, name, action, warnings, path):
    """Flip a .mcp.json server between the enabled/disabled arrays of a project
    entry. Mutates only lists — the string "all" is left as-is (it already
    covers every server), except that a denylist "all" makes enable impossible."""
    add_key, rem_key = (("enabledMcpjsonServers", "disabledMcpjsonServers")
                        if action == "enable"
                        else ("disabledMcpjsonServers", "enabledMcpjsonServers"))
    rem = entry.get(rem_key)
    if isinstance(rem, list):
        entry[rem_key] = [n for n in rem if n != name]
    elif rem == "all" and action == "enable":
        warnings.append('%s has disabledMcpjsonServers: "all" — enabling %r via '
                        "the project entry won't take effect; the denylist wins."
                        % (home_short(path), name))
    if entry.get(add_key) == "all":
        return  # "all" already covers the target state
    lst = entry.setdefault(add_key, [])
    if isinstance(lst, list) and name not in lst:
        lst.append(name)


def cmd_apply(args):
    with open(args.changes_file, "r", encoding="utf-8") as f:
        changes, visibility, mode = parse_changes(f.read())
    if not changes and not visibility["hide"] and not visibility["show"] and not mode:
        sys.exit("Nothing to apply: the block contains no enable/disable/hide/show/mode lines.")

    config = read_json(CLAUDE_JSON)
    if config is None:
        sys.exit("ERROR: cannot read %s" % CLAUDE_JSON)
    raw_projects = config.get("projects") or {}
    data, mcpjson_names = collect(include_missing=True)
    known_names = set(s["name"] for s in data["servers"])
    denied = load_denied_servers()

    state = load_state()
    hidden = set(state.get("hiddenProjects") or [])
    vis_log = []
    ui_mode = "cli" if state.get("uiMode") == "cli" else "desktop"  # desktop is the default
    if mode and mode != ui_mode:
        vis_log.append("mode: %s (dashboard only)" % mode)
    if mode:
        ui_mode = mode
    for path in visibility["hide"]:
        if path not in raw_projects:
            sys.exit("ERROR: project %r (hide:) not found in ~/.claude.json — "
                     "re-run `build` and copy a fresh block." % path)
        hidden.add(path)
        vis_log.append("hide %s (dashboard only)" % home_short(path))
    for path in visibility["show"]:
        hidden.discard(path)
        vis_log.append("show %s (dashboard only)" % home_short(path))

    log, warnings = [], []
    for change in changes:
        path = change["project"]
        entry = raw_projects.get(path)
        if entry is None:
            sys.exit("ERROR: project %r not found in ~/.claude.json — "
                     "re-run `build` and copy a fresh block." % path)
        in_mcpjson = mcpjson_names.get(path, set())
        for name in change.get("add") or []:
            if name in (config.get("mcpServers") or {}):
                warnings.append("%r is a global (user-scope) server — it is already "
                                "available in every project; nothing to add." % name)
                continue
            sources = []   # (project path, raw definition) — copied config-to-config
            for spath in sorted(raw_projects):
                defn = (raw_projects[spath].get("mcpServers") or {}).get(name)
                if defn is not None:
                    sources.append((spath, defn))
            if sources:   # local-scope server: copy inside ~/.claude.json
                src_path, defn = sources[0]
                servers_map = entry.setdefault("mcpServers", {})
                if name in servers_map:
                    warnings.append("%r is already connected in %s — just making "
                                    "sure it is enabled." % (name, home_short(path)))
                else:
                    if len({json.dumps(d, sort_keys=True) for _, d in sources}) > 1:
                        warnings.append("%r is configured differently in %d projects "
                                        "— copied the version from %s."
                                        % (name, len(sources), home_short(src_path)))
                    servers_map[name] = json.loads(json.dumps(defn))
                    log.append("add %s in %s (config copied from %s)"
                               % (name, home_short(path), home_short(src_path)))
                dis = entry.get("disabledMcpServers")
                if isinstance(dis, list) and name in dis:
                    dis[:] = [n for n in dis if n != name]
                    log.append("enable %s in %s" % (name, home_short(path)))
                continue
            # no local definition — maybe it lives in some repo's .mcp.json;
            # then "add" means: merge the entry into the TARGET repo's .mcp.json
            # (the one file this script touches outside ~/.claude.json) + approve it
            json_sources = []
            for spath in sorted(raw_projects):
                defn = ((read_json(os.path.join(spath, ".mcp.json")) or {})
                        .get("mcpServers") or {}).get(name)
                if defn is not None:
                    json_sources.append((spath, defn))
            if not json_sources:
                warnings.append("%r has no definition to copy — connect it with "
                                "the connect-mcp skill instead." % name)
                continue
            src_path, defn = json_sources[0]
            if len({json.dumps(d, sort_keys=True) for _, d in json_sources}) > 1:
                warnings.append("%r is configured differently in %d repos — copied "
                                "the version from %s."
                                % (name, len(json_sources), home_short(src_path)))
            if not os.path.isdir(path):
                warnings.append("%s does not exist on disk — cannot write its "
                                ".mcp.json; %r not added." % (home_short(path), name))
                continue
            target_file = os.path.join(path, ".mcp.json")
            target = read_json(target_file)
            if target is None and os.path.exists(target_file):
                warnings.append("%s is not valid JSON — fix it by hand; %r not added."
                                % (target_file, name))
                continue
            target = target or {}
            tmap = target.setdefault("mcpServers", {})
            if name in tmap:
                warnings.append("%r is already in %s — just approving it."
                                % (name, home_short(target_file)))
            else:
                tmap[name] = json.loads(json.dumps(defn))
                if not args.dry_run:
                    try:
                        fd, tmp = tempfile.mkstemp(dir=path, prefix=".mcp.json.")
                        with os.fdopen(fd, "w", encoding="utf-8") as f:
                            json.dump(target, f, ensure_ascii=False, indent=2)
                            f.write("\n")
                        os.replace(tmp, target_file)
                    except OSError as e:
                        warnings.append("cannot write %s (%s) — %r not added."
                                        % (target_file, e, name))
                        continue
                log.append("add %s in %s (.mcp.json entry copied from %s)"
                           % (name, home_short(path), home_short(src_path)))
            _toggle_mcpjson(entry, name, "enable", warnings, path)
            log.append("approve %s in %s (.mcp.json)" % (name, home_short(path)))
        for name in change.get("cleanup") or []:
            if name in known_names:
                warnings.append("%r is a live server, not a leftover — cleanup "
                                "skipped; use enable/disable instead." % name)
                continue
            removed = False
            for lkey in ("disabledMcpServers",
                         "enabledMcpjsonServers", "disabledMcpjsonServers"):
                lst = entry.get(lkey)
                if isinstance(lst, list) and name in lst:
                    lst[:] = [n for n in lst if n != name]
                    removed = True
            if name in denied:
                warnings.append("%r is also listed in deniedMcpServers in "
                                "~/.claude/settings.json — the script doesn't edit "
                                "that file; remove the entry there manually." % name)
            if removed:
                log.append("cleanup %s in %s" % (name, home_short(path)))
            else:
                warnings.append("%r has no leftover entries in %s — nothing to clean."
                                % (name, home_short(path)))
        for action in ("enable", "disable"):
            for name in change[action]:
                if name not in known_names:
                    warnings.append("%r is not a server name the dashboard knows — "
                                    "applied anyway (normal for a claude.ai connector "
                                    "never toggled before; double-check for typos)." % name)
                if action == "enable" and name in denied:
                    warnings.append("%r is blocked by deniedMcpServers in "
                                    "~/.claude/settings.json — per-project enable "
                                    "won't unblock it; remove it there instead." % name)
                if ui_mode == "desktop" and name.startswith(CONNECTOR_PREFIX):
                    warnings.append("%r is a claude.ai connector and the dashboard "
                                    "mode is Desktop — the Claude Desktop app pulls "
                                    "connectors from the account and ignores per-project "
                                    "config, so it won't notice this change (it still "
                                    "applies to CLI/IDE sessions). In Desktop, manage "
                                    "connectors via the tools icon in the app or by "
                                    "unlinking on claude.ai." % name)
                if name in in_mcpjson:
                    pinned = load_project_settings(path)
                    for key in ("enabledMcpjsonServers", "disabledMcpjsonServers"):
                        v = pinned.get(key)
                        if v == "all" or (isinstance(v, list) and name in v):
                            warnings.append(
                                "%r is pinned in %s/.claude/settings*.json (%s) — that "
                                "file wins over this change; edit it if the toggle "
                                "doesn't take effect." % (name, home_short(path), key))
                    _toggle_mcpjson(entry, name, action, warnings, path)
                else:
                    dis = entry.setdefault("disabledMcpServers", [])
                    if action == "disable" and name not in dis:
                        dis.append(name)
                    elif action == "enable":
                        dis[:] = [n for n in dis if n != name]
                log.append("%s %s in %s" % (action, name, home_short(path)))

    if args.dry_run:
        print("DRY RUN — nothing written. Would apply:")
        print("\n".join("  " + l for l in log + vis_log))
        for w in warnings:
            print("WARNING: " + w)
        return

    backup = None
    if log:  # ~/.claude.json is touched only for real server changes
        target = os.path.realpath(CLAUDE_JSON)  # keep symlinked configs intact
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = target + ".bak-mcpdash-" + stamp
        shutil.copy2(target, backup)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(target), prefix=".claude.json.")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        os.replace(tmp, target)
    if vis_log:
        state["hiddenProjects"] = sorted(hidden)
        if mode:
            state["uiMode"] = mode
        save_state(state)

    print("Applied %d change(s):" % len(log + vis_log))
    print("\n".join("  " + l for l in log + vis_log))
    for w in warnings:
        print("WARNING: " + w)
    if backup:
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
