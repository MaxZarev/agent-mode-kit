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
        import mcp_dashboard
        self.mod = importlib.reload(mcp_dashboard)

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("CLAUDE_CONFIG_DIR", None)

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
        changes, vis = self.mod.parse_changes(
            "=== MCP CHANGES ===\n"
            "hide: /a\nshow: /b\n"
            "project: /p\nenable: x, claude.ai Gmail\ndisable: y\n"
            "=== END ===")
        self.assertEqual(vis, {"hide": ["/a"], "show": ["/b"]})
        self.assertEqual(changes, [{"project": "/p",
                                    "enable": ["x", "claude.ai Gmail"],
                                    "disable": ["y"]}])

    def test_windows_path_value_keeps_colon(self):
        changes, _ = self.mod.parse_changes(
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

    def test_denied_server_state_blk(self):
        proj = self.make_project()
        self.write_config({
            "mcpServers": {"context7": {"type": "http", "url": "https://c7/mcp"}},
            "projects": {proj: {}}})
        with open(os.path.join(self.dir, "settings.json"), "w") as f:
            json.dump({"deniedMcpServers": [{"serverName": "context7"}]}, f)
        data, _ = self.mod.collect()
        self.assertEqual(data["states"]["context7"][proj], "blk")

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
