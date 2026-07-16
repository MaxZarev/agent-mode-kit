#!/usr/bin/env python3
"""Tests for mcp_dashboard.py — stdlib unittest only.

Run:  python3 skills/mcp-dashboard/scripts/test_mcp_dashboard.py
Everything operates on a throwaway CLAUDE_CONFIG_DIR; the real ~/.claude.json
is never touched.
"""

import contextlib
import importlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MASK = "•••"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        os.environ["CLAUDE_CONFIG_DIR"] = self.dir
        # point HOME/APPDATA into the sandbox too, so connector discovery never
        # sees the real Claude Desktop data of the machine running the tests
        self._env = {k: os.environ.get(k)
                     for k in ("HOME", "APPDATA", "USERPROFILE")}
        for k in self._env:
            os.environ[k] = self.dir
        import mcp_dashboard
        self.mod = importlib.reload(mcp_dashboard)

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def write_config(self, cfg):
        with open(os.path.join(self.dir, ".claude.json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f)

    def read_config(self):
        with open(os.path.join(self.dir, ".claude.json"), encoding="utf-8") as f:
            return json.load(f)

    def run_cli(self, *argv):
        out = io.StringIO()
        old = sys.argv
        sys.argv = ["mcp_dashboard.py"] + list(argv)
        try:
            with contextlib.redirect_stdout(out):
                self.mod.main()
        finally:
            sys.argv = old
        return out.getvalue()

    def make_project(self, name="proj"):
        path = os.path.join(self.dir, name)
        os.makedirs(path, exist_ok=True)
        return path


class TestRedaction(Base):
    def test_url_userinfo_masked(self):
        out = self.mod.redact_url("https://user:hunter2@example.com/mcp")
        self.assertNotIn("hunter2", out)
        self.assertIn(MASK + "@example.com", out)

    def test_url_fragment_masked(self):
        out = self.mod.redact_url("https://example.com/mcp#token=SECRETSECRETSECRET")
        self.assertNotIn("SECRET", out)
        self.assertIn("#" + MASK, out)

    def test_url_query_masked(self):
        out = self.mod.redact_url("https://example.com/api?token=secret123")
        self.assertNotIn("secret123", out)

    def test_url_tokenish_path_segment_masked(self):
        out = self.mod.redact_url("https://example.com/AKIAIOSFODNN7EXAMPLETOKEN/sse")
        self.assertNotIn("AKIA", out)
        self.assertTrue(out.endswith("/sse"))

    def test_non_url_returned_as_is(self):
        self.assertEqual(self.mod.redact_url("not a url"), "not a url")

    def test_args_paths_not_masked(self):
        args = ["npx", "-y", "@modelcontextprotocol/server-filesystem",
                "/Users/someone/Documents/projects"]
        self.assertEqual(self.mod.redact_args(args), args)

    def test_args_windows_path_not_masked(self):
        args = ["node", r"C:\Users\someone\mcp\server-something.js"]
        self.assertEqual(self.mod.redact_args(args), args)

    def test_args_long_token_masked(self):
        out = self.mod.redact_args(["srv", "abcDEF0123456789abcdef012345"])
        self.assertEqual(out[1], MASK)

    def test_args_value_after_secret_flag_masked(self):
        out = self.mod.redact_args(["srv", "--api-key", "/looks/like/path"])
        self.assertEqual(out[2], MASK)

    def test_args_url_with_token_redacted(self):
        out = self.mod.redact_args(["srv", "https://example.com/api?token=verysecret"])
        self.assertNotIn("verysecret", out[1])

    def test_args_non_string_values_survive(self):
        out = self.mod.redact_args(["srv", 8080, True])
        self.assertEqual(out, ["srv", "8080", "True"])


class TestMcpjsonState(Base):
    def test_default_is_ask(self):
        self.assertEqual(self.mod.mcpjson_state("x", {}, {}), "ask")

    def test_enabled_all_string(self):
        self.assertEqual(
            self.mod.mcpjson_state("x", {"enabledMcpjsonServers": "all"}, {}), "on")

    def test_denylist_wins(self):
        entry = {"enabledMcpjsonServers": ["x"], "disabledMcpjsonServers": ["x"]}
        self.assertEqual(self.mod.mcpjson_state("x", entry, {}), "off")

    def test_settings_override_entry(self):
        entry = {"enabledMcpjsonServers": ["x"]}
        settings = {"enabledMcpjsonServers": []}
        self.assertEqual(self.mod.mcpjson_state("x", entry, settings), "ask")


class TestParseChanges(Base):
    def test_full_block(self):
        changes, vis, mode, blocks = self.mod.parse_changes(
            "=== MCP CHANGES ===\n"
            "mode: desktop\n"
            "hide: /a\nshow: /b\n"
            "unblock: claude.ai Notion\n"
            "project: /p\nadd: exa\nenable: x, claude.ai Gmail\ndisable: y\n"
            "cleanup: old-one\n"
            "=== END ===")
        self.assertEqual(vis, {"hide": ["/a"], "show": ["/b"]})
        self.assertEqual(mode, "desktop")
        self.assertEqual(blocks, {"block": [], "unblock": ["claude.ai Notion"]})
        self.assertEqual(changes, [{"project": "/p",
                                    "enable": ["x", "claude.ai Gmail"],
                                    "disable": ["y"],
                                    "cleanup": ["old-one"],
                                    "add": ["exa"]}])

    def test_cleanup_only_block_kept(self):
        changes, _, _, _ = self.mod.parse_changes("project: /p\ncleanup: ghost\n")
        self.assertEqual(changes, [{"project": "/p", "enable": [],
                                    "disable": [], "cleanup": ["ghost"],
                                    "add": []}])

    def test_block_lines_are_position_independent(self):
        _, _, _, blocks = self.mod.parse_changes(
            "project: /p\ndisable: x\nblock: bad-one, worse-one\nunblock: y\n")
        self.assertEqual(blocks, {"block": ["bad-one", "worse-one"],
                                  "unblock": ["y"]})

    def test_no_mode_line_is_none(self):
        _, _, mode, _ = self.mod.parse_changes("project: /p\ndisable: srv\n")
        self.assertIsNone(mode)

    def test_bad_mode_exits(self):
        with self.assertRaises(SystemExit):
            self.mod.parse_changes("mode: web\n")

    def test_windows_path_value_keeps_colon(self):
        changes, _, _, _ = self.mod.parse_changes(
            "project: C:\\Users\\x\\proj\ndisable: srv\n")
        self.assertEqual(changes[0]["project"], "C:\\Users\\x\\proj")

    def test_garbage_line_exits(self):
        with self.assertRaises(SystemExit):
            self.mod.parse_changes("what is this")


class TestApply(Base):
    def base_config(self, project):
        return {
            "mcpServers": {"context7": {"type": "http", "url": "https://c7/mcp"}},
            "projects": {project: {"mcpServers": {},
                                   "disabledMcpServers": ["context7"]}},
        }

    def write_changes(self, text):
        p = os.path.join(self.dir, "changes.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p

    def test_enable_and_disable_roundtrip(self):
        proj = self.make_project()
        self.write_config(self.base_config(proj))
        ch = self.write_changes("project: %s\nenable: context7\ndisable: todoist\n" % proj)
        out = self.run_cli("apply", ch)
        entry = self.read_config()["projects"][proj]
        self.assertEqual(entry["disabledMcpServers"], ["todoist"])
        self.assertIn("Backup:", out)

    def test_unknown_name_warns_but_applies(self):
        proj = self.make_project()
        self.write_config(self.base_config(proj))
        ch = self.write_changes("project: %s\ndisable: tipo-with-typo\n" % proj)
        out = self.run_cli("apply", ch)
        self.assertIn("WARNING", out)
        self.assertIn("tipo-with-typo",
                      self.read_config()["projects"][proj]["disabledMcpServers"])

    def test_unknown_project_exits(self):
        proj = self.make_project()
        self.write_config(self.base_config(proj))
        ch = self.write_changes("project: /nope\ndisable: context7\n")
        with self.assertRaises(SystemExit):
            self.run_cli("apply", ch)

    def test_visibility_only_skips_config_write(self):
        proj = self.make_project()
        cfg = self.base_config(proj)
        self.write_config(cfg)
        ch = self.write_changes("hide: %s\n" % proj)
        out = self.run_cli("apply", ch)
        self.assertNotIn("Backup:", out)
        self.assertEqual(self.read_config(), cfg)
        state = json.load(open(os.path.join(self.dir, "mcp-dashboard.json")))
        self.assertEqual(state["hiddenProjects"], [proj])

    def test_mcpjson_all_string_no_crash(self):
        proj = self.make_project()
        with open(os.path.join(proj, ".mcp.json"), "w") as f:
            json.dump({"mcpServers": {"sandbox": {"command": "npx"}}}, f)
        cfg = self.base_config(proj)
        cfg["projects"][proj]["enabledMcpjsonServers"] = "all"
        cfg["projects"][proj]["disabledMcpjsonServers"] = "all"
        self.write_config(cfg)
        ch = self.write_changes("project: %s\nenable: sandbox\n" % proj)
        out = self.run_cli("apply", ch)  # must not raise TypeError
        self.assertIn('disabledMcpjsonServers: "all"', out)
        entry = self.read_config()["projects"][proj]
        self.assertEqual(entry["enabledMcpjsonServers"], "all")  # left intact

    def test_denied_enable_warns(self):
        proj = self.make_project()
        self.write_config(self.base_config(proj))
        with open(os.path.join(self.dir, "settings.json"), "w") as f:
            json.dump({"deniedMcpServers": [{"serverName": "context7"}]}, f)
        ch = self.write_changes("project: %s\nenable: context7\n" % proj)
        out = self.run_cli("apply", ch)
        self.assertIn("deniedMcpServers", out)

    def test_mode_only_saves_state_without_backup(self):
        proj = self.make_project()
        cfg = self.base_config(proj)
        self.write_config(cfg)
        ch = self.write_changes("mode: cli\n")
        out = self.run_cli("apply", ch)
        self.assertNotIn("Backup:", out)
        self.assertEqual(self.read_config(), cfg)
        state = json.load(open(os.path.join(self.dir, "mcp-dashboard.json")))
        self.assertEqual(state["uiMode"], "cli")

    def test_connector_toggle_warns_in_desktop_mode(self):
        # no uiMode in state -> desktop is the default
        proj = self.make_project()
        self.write_config(self.base_config(proj))
        ch = self.write_changes("project: %s\ndisable: claude.ai Gmail\n" % proj)
        out = self.run_cli("apply", ch)
        self.assertIn("Claude Desktop", out)
        self.assertIn("claude.ai Gmail",
                      self.read_config()["projects"][proj]["disabledMcpServers"])

    def test_connector_toggle_silent_in_cli_mode(self):
        proj = self.make_project()
        self.write_config(self.base_config(proj))
        ch = self.write_changes("mode: cli\nproject: %s\ndisable: claude.ai Gmail\n" % proj)
        out = self.run_cli("apply", ch)
        self.assertNotIn("Claude Desktop", out)

    def test_add_copies_local_definition(self):
        src, dst = self.make_project("src"), self.make_project("dst")
        defn = {"type": "http", "url": "https://exa/mcp",
                "headers": {"X-Api-Key": "RAWSECRET123"}}
        self.write_config({
            "mcpServers": {},
            "projects": {src: {"mcpServers": {"exa": defn}},
                         dst: {"mcpServers": {},
                               "disabledMcpServers": ["exa"]}}})
        ch = self.write_changes("project: %s\nadd: exa\n" % dst)
        out = self.run_cli("apply", ch)
        entry = self.read_config()["projects"][dst]
        self.assertEqual(entry["mcpServers"]["exa"], defn)
        self.assertEqual(entry["disabledMcpServers"], [])
        self.assertIn("add exa", out)
        self.assertIn("Backup:", out)
        self.assertNotIn("RAWSECRET123", out)  # secrets never printed

    def test_add_global_server_warns_and_skips(self):
        proj = self.make_project()
        self.write_config(self.base_config(proj))
        ch = self.write_changes("project: %s\nadd: context7\n" % proj)
        out = self.run_cli("apply", ch)
        self.assertIn("user-scope", out)
        self.assertNotIn("mcpServers", self.read_config()["projects"][proj].get(
            "mcpServers", {}))

    def test_add_already_connected_just_enables(self):
        proj = self.make_project()
        defn = {"command": "npx", "args": ["exa-mcp"]}
        self.write_config({
            "mcpServers": {},
            "projects": {proj: {"mcpServers": {"exa": defn},
                                "disabledMcpServers": ["exa"]}}})
        ch = self.write_changes("project: %s\nadd: exa\n" % proj)
        out = self.run_cli("apply", ch)
        entry = self.read_config()["projects"][proj]
        self.assertEqual(entry["mcpServers"]["exa"], defn)  # not duplicated/overwritten
        self.assertEqual(entry["disabledMcpServers"], [])
        self.assertIn("already connected", out)

    def test_add_mcpjson_writes_target_repo_file_and_approves(self):
        src, dst = self.make_project("src"), self.make_project("dst")
        defn = {"command": "npx", "args": ["sandbox-mcp"]}
        with open(os.path.join(src, ".mcp.json"), "w") as f:
            json.dump({"mcpServers": {"sandbox": defn}}, f)
        self.write_config({"mcpServers": {},
                           "projects": {src: {}, dst: {}}})
        ch = self.write_changes("project: %s\nadd: sandbox\n" % dst)
        out = self.run_cli("apply", ch)
        target = json.load(open(os.path.join(dst, ".mcp.json")))
        self.assertEqual(target["mcpServers"]["sandbox"], defn)
        entry = self.read_config()["projects"][dst]
        self.assertIn("sandbox", entry["enabledMcpjsonServers"])
        self.assertIn(".mcp.json entry copied from", out)

    def test_add_mcpjson_merges_into_existing_file(self):
        src, dst = self.make_project("src"), self.make_project("dst")
        with open(os.path.join(src, ".mcp.json"), "w") as f:
            json.dump({"mcpServers": {"sandbox": {"command": "npx"}}}, f)
        with open(os.path.join(dst, ".mcp.json"), "w") as f:
            json.dump({"mcpServers": {"other": {"command": "uvx"}}}, f)
        self.write_config({"mcpServers": {}, "projects": {src: {}, dst: {}}})
        ch = self.write_changes("project: %s\nadd: sandbox\n" % dst)
        self.run_cli("apply", ch)
        target = json.load(open(os.path.join(dst, ".mcp.json")))
        self.assertEqual(set(target["mcpServers"]), {"other", "sandbox"})

    def test_add_mcpjson_already_present_just_approves(self):
        proj = self.make_project()
        with open(os.path.join(proj, ".mcp.json"), "w") as f:
            json.dump({"mcpServers": {"sandbox": {"command": "npx"}}}, f)
        self.write_config({"mcpServers": {}, "projects": {proj: {}}})
        ch = self.write_changes("project: %s\nadd: sandbox\n" % proj)
        out = self.run_cli("apply", ch)
        self.assertIn("already in", out)
        self.assertIn("sandbox",
                      self.read_config()["projects"][proj]["enabledMcpjsonServers"])

    def test_add_mcpjson_invalid_target_file_untouched(self):
        src, dst = self.make_project("src"), self.make_project("dst")
        with open(os.path.join(src, ".mcp.json"), "w") as f:
            json.dump({"mcpServers": {"sandbox": {"command": "npx"}}}, f)
        with open(os.path.join(dst, ".mcp.json"), "w") as f:
            f.write("{broken json")
        self.write_config({"mcpServers": {}, "projects": {src: {}, dst: {}}})
        ch = self.write_changes("project: %s\nadd: sandbox\n" % dst)
        out = self.run_cli("apply", ch)
        self.assertIn("not valid JSON", out)
        self.assertEqual(open(os.path.join(dst, ".mcp.json")).read(), "{broken json")

    def test_add_mcpjson_dry_run_writes_nothing(self):
        src, dst = self.make_project("src"), self.make_project("dst")
        with open(os.path.join(src, ".mcp.json"), "w") as f:
            json.dump({"mcpServers": {"sandbox": {"command": "npx"}}}, f)
        cfg = {"mcpServers": {}, "projects": {src: {}, dst: {}}}
        self.write_config(cfg)
        ch = self.write_changes("project: %s\nadd: sandbox\n" % dst)
        out = self.run_cli("apply", ch, "--dry-run")
        self.assertIn("DRY RUN", out)
        self.assertFalse(os.path.exists(os.path.join(dst, ".mcp.json")))
        self.assertEqual(self.read_config(), cfg)

    def test_add_without_source_warns(self):
        proj = self.make_project()
        self.write_config(self.base_config(proj))
        ch = self.write_changes("project: %s\nadd: nosuch\n" % proj)
        out = self.run_cli("apply", ch)
        self.assertIn("connect-mcp", out)
        self.assertNotIn("nosuch", json.dumps(
            self.read_config()["projects"][proj].get("mcpServers", {})))

    def test_unblock_removes_from_both_settings_files(self):
        proj = self.make_project()
        self.write_config(self.base_config(proj))
        with open(os.path.join(self.dir, "settings.json"), "w") as f:
            json.dump({"deniedMcpServers": [{"serverName": "context7"}],
                       "otherKey": True}, f)
        with open(os.path.join(self.dir, "settings.local.json"), "w") as f:
            json.dump({"deniedMcpServers": ["context7", "keepme"]}, f)
        ch = self.write_changes("unblock: context7\n")
        out = self.run_cli("apply", ch)
        s1 = json.load(open(os.path.join(self.dir, "settings.json")))
        s2 = json.load(open(os.path.join(self.dir, "settings.local.json")))
        self.assertEqual(s1["deniedMcpServers"], [])
        self.assertTrue(s1["otherKey"])          # untouched keys preserved
        self.assertEqual(s2["deniedMcpServers"], ["keepme"])
        self.assertIn("unblock context7", out)
        self.assertIn("Settings backup:", out)
        self.assertNotIn("Backup:", out.replace("Settings backup:", ""))  # config untouched

    def test_unblock_unknown_warns(self):
        proj = self.make_project()
        self.write_config(self.base_config(proj))
        ch = self.write_changes("unblock: never-blocked\n")
        out = self.run_cli("apply", ch)
        self.assertIn("not blocked", out)

    def test_block_adds_to_settings(self):
        proj = self.make_project()
        self.write_config(self.base_config(proj))
        ch = self.write_changes("block: risky-one\n")
        out = self.run_cli("apply", ch)
        s = json.load(open(os.path.join(self.dir, "settings.json")))
        self.assertIn({"serverName": "risky-one"}, s["deniedMcpServers"])
        self.assertIn("block risky-one", out)

    def test_unblock_then_enable_has_no_denied_warning(self):
        proj = self.make_project()
        self.write_config(self.base_config(proj))
        with open(os.path.join(self.dir, "settings.json"), "w") as f:
            json.dump({"deniedMcpServers": ["context7"]}, f)
        ch = self.write_changes(
            "unblock: context7\nproject: %s\nenable: context7\n" % proj)
        out = self.run_cli("apply", ch)
        self.assertNotIn("won't unblock", out)
        self.assertEqual(self.read_config()["projects"][proj]["disabledMcpServers"], [])

    def test_unblock_dry_run_writes_nothing(self):
        proj = self.make_project()
        self.write_config(self.base_config(proj))
        with open(os.path.join(self.dir, "settings.json"), "w") as f:
            json.dump({"deniedMcpServers": ["context7"]}, f)
        ch = self.write_changes("unblock: context7\n")
        out = self.run_cli("apply", ch, "--dry-run")
        self.assertIn("DRY RUN", out)
        s = json.load(open(os.path.join(self.dir, "settings.json")))
        self.assertEqual(s["deniedMcpServers"], ["context7"])

    def test_cleanup_removes_stale_entries_everywhere(self):
        proj = self.make_project()
        cfg = self.base_config(proj)
        cfg["projects"][proj]["disabledMcpServers"] = ["context7", "goner"]
        cfg["projects"][proj]["enabledMcpjsonServers"] = ["goner"]
        cfg["projects"][proj]["disabledMcpjsonServers"] = ["goner"]
        self.write_config(cfg)
        ch = self.write_changes("project: %s\ncleanup: goner\n" % proj)
        out = self.run_cli("apply", ch)
        entry = self.read_config()["projects"][proj]
        self.assertEqual(entry["disabledMcpServers"], ["context7"])
        self.assertEqual(entry["enabledMcpjsonServers"], [])
        self.assertEqual(entry["disabledMcpjsonServers"], [])
        self.assertIn("Backup:", out)

    def test_cleanup_of_live_server_skipped(self):
        proj = self.make_project()
        self.write_config(self.base_config(proj))
        ch = self.write_changes("project: %s\ncleanup: context7\n" % proj)
        out = self.run_cli("apply", ch)
        self.assertIn("live server", out)
        self.assertIn("context7",
                      self.read_config()["projects"][proj]["disabledMcpServers"])

    def test_cleanup_of_denied_ghost_warns_about_settings(self):
        proj = self.make_project()
        cfg = self.base_config(proj)
        cfg["projects"][proj]["disabledMcpServers"] = ["goner"]
        self.write_config(cfg)
        with open(os.path.join(self.dir, "settings.json"), "w") as f:
            json.dump({"deniedMcpServers": [{"serverName": "goner"}]}, f)
        ch = self.write_changes("project: %s\ncleanup: goner\n" % proj)
        out = self.run_cli("apply", ch)
        self.assertIn("settings.json", out)
        self.assertEqual(self.read_config()["projects"][proj]["disabledMcpServers"], [])


class TestBuildAndCollect(Base):
    def test_build_writes_html_and_detects_new_projects(self):
        proj = self.make_project("one")
        self.write_config({"mcpServers": {}, "projects": {proj: {}}})
        out_dir = os.path.join(self.dir, "out")
        first = self.run_cli("build", "--out", out_dir)
        self.assertIn("FIRST RUN", first)
        html = open(os.path.join(out_dir, "mcp-dashboard.html"), encoding="utf-8").read()
        self.assertNotIn("/*__MCP_DATA__*/null", html)

        proj2 = self.make_project("two")
        self.write_config({"mcpServers": {}, "projects": {proj: {}, proj2: {}}})
        second = self.run_cli("build", "--out", out_dir)
        self.assertIn("NEW PROJECT: %s" % proj2, second)

    def test_build_injects_ui_mode_desktop_by_default(self):
        proj = self.make_project()
        self.write_config({"mcpServers": {}, "projects": {proj: {}}})
        out_dir = os.path.join(self.dir, "out")
        self.run_cli("build", "--out", out_dir)
        html = open(os.path.join(out_dir, "mcp-dashboard.html"), encoding="utf-8").read()
        self.assertIn('"uiMode": "desktop"', html)

    def test_build_respects_cli_mode_from_state(self):
        proj = self.make_project()
        self.write_config({"mcpServers": {}, "projects": {proj: {}}})
        with open(os.path.join(self.dir, "mcp-dashboard.json"), "w") as f:
            json.dump({"uiMode": "cli"}, f)
        out_dir = os.path.join(self.dir, "out")
        self.run_cli("build", "--out", out_dir)
        html = open(os.path.join(out_dir, "mcp-dashboard.html"), encoding="utf-8").read()
        self.assertIn('"uiMode": "cli"', html)

    def test_denied_server_flagged_with_underlying_state(self):
        proj = self.make_project()
        self.write_config({
            "mcpServers": {"context7": {"type": "http", "url": "https://c7/mcp"}},
            "projects": {proj: {}}})
        with open(os.path.join(self.dir, "settings.json"), "w") as f:
            json.dump({"deniedMcpServers": [{"serverName": "context7"}]}, f)
        data, _ = self.mod.collect()
        srv = {s["name"]: s for s in data["servers"]}["context7"]
        self.assertTrue(srv["denied"])
        # underlying state kept so the page can preview a pending unblock
        self.assertEqual(data["states"]["context7"][proj], "on")

    def test_ghost_not_a_server_column(self):
        proj = self.make_project()
        self.write_config({
            "mcpServers": {"context7": {"type": "http", "url": "https://c7/mcp"}},
            "projects": {proj: {"disabledMcpServers": ["goner"]}}})
        data, _ = self.mod.collect()
        self.assertNotIn("goner", [s["name"] for s in data["servers"]])
        self.assertEqual(len(data["ghosts"]), 1)
        g = data["ghosts"][0]
        self.assertEqual(g["name"], "goner")
        self.assertFalse(g["denied"])
        self.assertEqual(g["projects"][0]["path"], proj)
        self.assertEqual(g["projects"][0]["sources"], ["disabledMcpServers"])

    def test_connector_and_plugin_get_their_groups(self):
        proj = self.make_project()
        self.write_config({
            "mcpServers": {},
            "projects": {proj: {"disabledMcpServers":
                                ["claude.ai Gmail", "plugin:foo@bar"]}}})
        data, _ = self.mod.collect()
        groups = {s["name"]: s["group"] for s in data["servers"]}
        self.assertEqual(groups["claude.ai Gmail"], "connector")
        self.assertEqual(groups["plugin:foo@bar"], "plugin")
        self.assertEqual(data["ghosts"], [])

    def test_builtin_server_is_not_ghost(self):
        proj = self.make_project()
        self.write_config({
            "mcpServers": {},
            "projects": {proj: {"disabledMcpServers": ["claude-in-chrome"]}}})
        data, _ = self.mod.collect()
        groups = {s["name"]: s["group"] for s in data["servers"]}
        self.assertEqual(groups["claude-in-chrome"], "builtin")
        self.assertEqual(data["ghosts"], [])
        self.assertEqual(data["states"]["claude-in-chrome"][proj], "off")

    def test_mcpjson_leftover_is_ghost(self):
        proj = self.make_project()
        self.write_config({
            "mcpServers": {},
            "projects": {proj: {"enabledMcpjsonServers": ["gone-json"]}}})
        data, _ = self.mod.collect()
        self.assertNotIn("gone-json", [s["name"] for s in data["servers"]])
        self.assertEqual(data["ghosts"][0]["projects"][0]["sources"],
                         ["enabledMcpjsonServers"])

    def test_denied_name_without_definition_is_denied_ghost(self):
        proj = self.make_project()
        self.write_config({"mcpServers": {}, "projects": {proj: {}}})
        with open(os.path.join(self.dir, "settings.json"), "w") as f:
            json.dump({"deniedMcpServers": ["goner"]}, f)
        data, _ = self.mod.collect()
        self.assertNotIn("goner", [s["name"] for s in data["servers"]])
        self.assertEqual(data["ghosts"][0]["name"], "goner")
        self.assertTrue(data["ghosts"][0]["denied"])
        self.assertEqual(data["ghosts"][0]["projects"], [])

    def test_build_prints_rudiment_lines(self):
        proj = self.make_project()
        self.write_config({
            "mcpServers": {},
            "projects": {proj: {"disabledMcpServers": ["goner"]}}})
        out = self.run_cli("build", "--out", os.path.join(self.dir, "out"))
        self.assertIn("RUDIMENT: goner", out)

    def test_secret_values_never_reach_payload(self):
        proj = self.make_project()
        self.write_config({
            "mcpServers": {
                "h": {"type": "http", "url": "https://u:PW12345@h.com/mcp?tok=QQ",
                      "headers": {"X-Key": "HEADERSECRET"}},
                "s": {"command": "npx", "args": ["--token", "ARGSECRET123"],
                      "env": {"API_KEY": "ENVSECRET"}}},
            "projects": {proj: {}}})
        data, _ = self.mod.collect()
        payload = json.dumps(data, ensure_ascii=False)
        for secret in ("PW12345", "tok=QQ", "HEADERSECRET", "ARGSECRET123", "ENVSECRET"):
            self.assertNotIn(secret, payload)


class TestDesktopDiscovery(Base):
    """discover_desktop_connectors() over a fake Claude Desktop data dir."""

    def setUp(self):
        super().setUp()
        self.root = os.path.join(self.dir, "DesktopData")

    def snap(self, fname, servers, mtime=None, raw=None):
        """Write a fake session snapshot. `servers` is a list of
        (name, uuid, {tool: True|False|None}) — None means "no uuid:tool key"."""
        d = os.path.join(self.root, "claude-code-sessions", "acc", "ws")
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, fname)
        if raw is None:
            remote, enabled = [], {}
            for name, uuid, tools in servers:
                remote.append({"uuid": uuid, "name": name,
                               "tools": [{"name": t} for t in tools]})
                for t, v in tools.items():
                    if v is not None:
                        enabled["%s:%s" % (uuid, t)] = v
            raw = json.dumps({"remoteMcpServersConfig": remote,
                              "enabledMcpTools": enabled})
        with open(path, "w", encoding="utf-8") as f:
            f.write(raw)
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def test_app_state_semantics(self):
        self.snap("local_a.json", [
            ("AllOff", "u1", {"t1": False, "t2": False}),
            ("AllOn", "u2", {"t1": True, "t2": True}),
            ("Mixed", "u3", {"t1": True, "t2": False}),
            ("NoKeys", "u4", {"t1": None, "t2": None}),      # default = on
            ("SomeKeys", "u5", {"t1": True, "t2": None}),    # still on
        ])
        found = self.mod.discover_desktop_connectors(root=self.root)
        states = {n: v["appState"] for n, v in found.items()}
        self.assertEqual(states, {"AllOff": "off", "AllOn": "on",
                                  "Mixed": "partial", "NoKeys": "on",
                                  "SomeKeys": "on"})
        self.assertEqual(found["AllOff"]["toolCount"], 2)

    def test_stale_uuid_entries_ignored(self):
        # enabledMcpTools keeps false entries under a uuid that is no longer
        # in remoteMcpServersConfig — they must not affect the live connector
        d = os.path.join(self.root, "claude-code-sessions", "acc", "ws")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "local_a.json"), "w") as f:
            json.dump({"remoteMcpServersConfig": [
                           {"uuid": "new", "name": "Srv",
                            "tools": [{"name": "t1"}, {"name": "t2"}]}],
                       "enabledMcpTools": {"old:t1": False, "old:t2": False}}, f)
        found = self.mod.discover_desktop_connectors(root=self.root)
        self.assertEqual(found["Srv"]["appState"], "on")

    def test_merge_freshest_wins_older_names_kept(self):
        self.snap("local_old.json", [
            ("Gmail", "u1", {"t": True}),
            ("Notion", "u2", {"t": True})], mtime=1000)
        self.snap("local_new.json", [
            ("Gmail", "u1", {"t": False})], mtime=2000)
        found = self.mod.discover_desktop_connectors(root=self.root)
        self.assertEqual(found["Gmail"]["appState"], "off")   # from the new file
        self.assertEqual(found["Notion"]["appState"], "on")   # not lost
        self.assertGreater(found["Gmail"]["snapshotAt"],
                           found["Notion"]["snapshotAt"])

    def test_snapshot_limit_respected(self):
        for i in range(10):
            self.snap("local_%d.json" % i,
                      [("Srv%d" % i, "u%d" % i, {"t": True})],
                      mtime=1000 + i)
        found = self.mod.discover_desktop_connectors(root=self.root)
        # only the 5 freshest files are read
        self.assertEqual(sorted(found),
                         ["Srv%d" % i for i in range(5, 10)])

    def test_broken_and_empty_files_skipped_silently(self):
        self.snap("local_broken.json", [], mtime=3000, raw="{not json")
        self.snap("local_empty.json", [], mtime=2900,
                  raw=json.dumps({"remoteMcpServersConfig": []}))
        self.snap("local_good.json", [("Srv", "u1", {"t": True})], mtime=2800)
        found = self.mod.discover_desktop_connectors(root=self.root)
        self.assertEqual(list(found), ["Srv"])

    def test_no_data_returns_none(self):
        self.assertIsNone(self.mod.discover_desktop_connectors(
            root=os.path.join(self.dir, "nowhere")))
        os.makedirs(os.path.join(self.root, "claude-code-sessions"),
                    exist_ok=True)   # dir exists but has no session files
        self.assertIsNone(self.mod.discover_desktop_connectors(root=self.root))

    def test_collect_discovers_and_dedups_with_disable_lists(self):
        proj = self.make_project()
        self.write_config({
            "mcpServers": {},
            "projects": {proj: {"disabledMcpServers": ["claude.ai Gmail"]}}})
        self.snap("local_a.json", [("Gmail", "u1", {"t1": True, "t2": True}),
                                   ("Drive", "u2", {"t1": True})])
        self.mod.desktop_root = lambda: self.root
        data, _ = self.mod.collect()
        srv = {s["name"]: s for s in data["servers"]}
        self.assertEqual(srv["claude.ai Gmail"]["group"], "connector")
        self.assertTrue(srv["claude.ai Gmail"]["discovered"])   # one column, enriched
        self.assertEqual(srv["claude.ai Gmail"]["appState"], "on")
        self.assertEqual(srv["claude.ai Gmail"]["toolCount"], 2)
        self.assertIn("snapshotAt", srv["claude.ai Gmail"])
        self.assertEqual(srv["claude.ai Drive"]["appState"], "on")
        # per-project cells still come from disabledMcpServers, not appState
        self.assertEqual(data["states"]["claude.ai Gmail"][proj], "off")
        self.assertEqual(data["states"]["claude.ai Drive"][proj], "on")
        self.assertEqual(data["ghosts"], [])

    def test_collect_without_desktop_data_has_no_discovered_fields(self):
        proj = self.make_project()
        self.write_config({
            "mcpServers": {},
            "projects": {proj: {"disabledMcpServers": ["claude.ai Gmail"]}}})
        data, _ = self.mod.collect()
        srv = {s["name"]: s for s in data["servers"]}["claude.ai Gmail"]
        self.assertEqual(srv["group"], "connector")
        self.assertNotIn("discovered", srv)
        self.assertNotIn("appState", srv)

    def test_apply_knows_discovered_connector(self):
        proj = self.make_project()
        self.write_config({"mcpServers": {}, "projects": {proj: {}}})
        self.snap("local_a.json", [("Gmail", "u1", {"t": True})])
        self.mod.desktop_root = lambda: self.root
        p = os.path.join(self.dir, "changes.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write("mode: cli\nproject: %s\ndisable: claude.ai Gmail\n" % proj)
        out = self.run_cli("apply", p)
        # a discovered connector is a known name — no typo warning
        self.assertNotIn("WARNING", out)
        self.assertIn("claude.ai Gmail",
                      self.read_config()["projects"][proj]["disabledMcpServers"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
