import collections
import os
import subprocess
from pathlib import Path
from typing import Dict
from unittest.mock import Mock

import pytest
from pylsp import uris
from pylsp.config.config import Config
from pylsp.workspace import Document, Workspace

from pylsp_mypy import plugin

DOC_URI = f"file:/{Path(__file__)}"
DOC_TYPE_ERR = """{}.append(3)
"""
TYPE_ERR_MSG = '"Dict[<nothing>, <nothing>]" has no attribute "append"'

TEST_LINE = 'test_plugin.py:279:8: error: "Request" has no attribute "id"'
TEST_LINE_WITHOUT_COL = "test_plugin.py:279: " 'error: "Request" has no attribute "id"'
TEST_LINE_WITHOUT_LINE = "test_plugin.py: " 'error: "Request" has no attribute "id"'

windows_flag: Dict[str, int] = (
    {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}  # type: ignore
)


@pytest.fixture
def last_diagnostics_monkeypatch(monkeypatch):
    # gets called before every test altering last_diagnostics in order to reset it
    monkeypatch.setattr(plugin, "last_diagnostics", collections.defaultdict(list))
    return monkeypatch


@pytest.fixture
def workspace(tmpdir):
    """Return a workspace."""
    ws = Workspace(uris.from_fs_path(str(tmpdir)), Mock())
    ws._config = Config(ws.root_uri, {}, 0, {})
    return ws


class FakeConfig(object):
    def __init__(self):
        self._root_path = "C://" if os.name == "nt" else "/"

    def plugin_settings(self, plugin, document_path=None):
        return {}


def test_settings():
    config = FakeConfig()
    settings = plugin.pylsp_settings(config)
    assert settings == {"plugins": {"pylsp_mypy": {}}}


def test_plugin(workspace, last_diagnostics_monkeypatch):
    config = FakeConfig()
    doc = Document(DOC_URI, workspace, DOC_TYPE_ERR)
    plugin.pylsp_settings(config)
    diags = plugin.pylsp_lint(config, workspace, doc, is_saved=False)

    assert len(diags) == 1
    diag = diags[0]
    assert diag["message"] == TYPE_ERR_MSG
    assert diag["range"]["start"] == {"line": 0, "character": 0}
    assert diag["range"]["end"] == {"line": 0, "character": 1}


def test_parse_full_line(workspace):
    doc = Document(DOC_URI, workspace)
    diag = plugin.parse_line(TEST_LINE, doc)
    assert diag["message"] == '"Request" has no attribute "id"'
    assert diag["range"]["start"] == {"line": 278, "character": 7}
    assert diag["range"]["end"] == {"line": 278, "character": 8}


def test_parse_line_without_col(workspace):
    doc = Document(DOC_URI, workspace)
    diag = plugin.parse_line(TEST_LINE_WITHOUT_COL, doc)
    assert diag["message"] == '"Request" has no attribute "id"'
    assert diag["range"]["start"] == {"line": 278, "character": 0}
    assert diag["range"]["end"] == {"line": 278, "character": 1}


def test_parse_line_without_line(workspace):
    doc = Document(DOC_URI, workspace)
    diag = plugin.parse_line(TEST_LINE_WITHOUT_LINE, doc)
    assert diag["message"] == '"Request" has no attribute "id"'
    assert diag["range"]["start"] == {"line": 0, "character": 0}
    assert diag["range"]["end"] == {"line": 0, "character": 6}


@pytest.mark.parametrize("word,bounds", [("", (7, 8)), ("my_var", (7, 13))])
def test_parse_line_with_context(monkeypatch, word, bounds, workspace):
    doc = Document(DOC_URI, workspace)
    monkeypatch.setattr(Document, "word_at_position", lambda *args: word)
    diag = plugin.parse_line(TEST_LINE, doc)
    assert diag["message"] == '"Request" has no attribute "id"'
    assert diag["range"]["start"] == {"line": 278, "character": bounds[0]}
    assert diag["range"]["end"] == {"line": 278, "character": bounds[1]}


def test_multiple_workspaces(tmpdir, last_diagnostics_monkeypatch):
    DOC_SOURCE = """
def foo():
    return
    unreachable = 1
"""
    DOC_ERR_MSG = "Statement is unreachable"

    # Initialize two workspace folders.
    folder1 = tmpdir.mkdir("folder1")
    ws1 = Workspace(uris.from_fs_path(str(folder1)), Mock())
    ws1._config = Config(ws1.root_uri, {}, 0, {})
    folder2 = tmpdir.mkdir("folder2")
    ws2 = Workspace(uris.from_fs_path(str(folder2)), Mock())
    ws2._config = Config(ws2.root_uri, {}, 0, {})

    # Create configuration file for workspace folder 1.
    mypy_config = folder1.join("mypy.ini")
    mypy_config.write("[mypy]\nwarn_unreachable = True\ncheck_untyped_defs = True")

    # Initialize settings for both folders.
    plugin.pylsp_settings(ws1._config)
    plugin.pylsp_settings(ws2._config)

    # Test document in workspace 1 (uses mypy.ini configuration).
    doc1 = Document(DOC_URI, ws1, DOC_SOURCE)
    diags = plugin.pylsp_lint(ws1._config, ws1, doc1, is_saved=False)
    assert len(diags) == 1
    diag = diags[0]
    assert diag["message"] == DOC_ERR_MSG

    # Test document in workspace 2 (without mypy.ini configuration)
    doc2 = Document(DOC_URI, ws2, DOC_SOURCE)
    diags = plugin.pylsp_lint(ws2._config, ws2, doc2, is_saved=False)
    assert len(diags) == 0


def test_apply_overrides():
    assert plugin.apply_overrides(["1", "2"], []) == []
    assert plugin.apply_overrides(["1", "2"], ["a"]) == ["a"]
    assert plugin.apply_overrides(["1", "2"], ["a", True]) == ["a", "1", "2"]
    assert plugin.apply_overrides(["1", "2"], [True, "a"]) == ["1", "2", "a"]
    assert plugin.apply_overrides(["1"], ["a", True, "b"]) == ["a", "1", "b"]


@pytest.mark.skipif(os.name == "nt", reason="Not working on Windows due to test design.")
def test_option_overrides(tmpdir, last_diagnostics_monkeypatch, workspace):
    import sys
    from stat import S_IRWXU
    from textwrap import dedent

    sentinel = tmpdir / "ran"

    source = dedent(
        """\
        #!{}
        import os, sys, pathlib
        pathlib.Path({!r}).touch()
        os.execv({!r}, sys.argv)
        """
    ).format(sys.executable, str(sentinel), sys.executable)

    wrapper = tmpdir / "bin/wrapper"
    wrapper.write(source, ensure=True)
    wrapper.chmod(S_IRWXU)

    overrides = ["--python-executable", wrapper.strpath, True]
    last_diagnostics_monkeypatch.setattr(
        FakeConfig,
        "plugin_settings",
        lambda _, p: {"overrides": overrides} if p == "pylsp_mypy" else {},
    )

    assert not sentinel.exists()

    diags = plugin.pylsp_lint(
        config=FakeConfig(),
        workspace=workspace,
        document=Document(DOC_URI, workspace, DOC_TYPE_ERR),
        is_saved=False,
    )
    assert len(diags) == 1
    assert sentinel.exists()


def test_option_overrides_dmypy(last_diagnostics_monkeypatch, workspace):
    overrides = ["--python-executable", "/tmp/fake", True]
    last_diagnostics_monkeypatch.setattr(
        FakeConfig,
        "plugin_settings",
        lambda _, p: {
            "overrides": overrides,
            "dmypy": True,
            "live_mode": False,
        }
        if p == "pylsp_mypy"
        else {},
    )

    m = Mock(wraps=lambda a, **_: Mock(returncode=0, **{"stdout.decode": lambda: ""}))
    last_diagnostics_monkeypatch.setattr(plugin.subprocess, "run", m)

    document = Document(DOC_URI, workspace, DOC_TYPE_ERR)

    plugin.pylsp_lint(
        config=FakeConfig(),
        workspace=workspace,
        document=document,
        is_saved=False,
    )
    expected = [
        "dmypy",
        "run",
        "--",
        "--python-executable",
        "/tmp/fake",
        "--show-column-numbers",
        document.path,
    ]
    m.assert_called_with(expected, stderr=-1, stdout=-1, **windows_flag)
