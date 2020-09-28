import pytest
from unittest.mock import Mock

from pyls import uris
from pyls.workspace import Document, Workspace
from pyls_mypy import plugin

DOC_URI = __file__
DOC_TYPE_ERR = """{}.append(3)
"""
TYPE_ERR_MSG = '"Dict[<nothing>, <nothing>]" has no attribute "append"'

TEST_LINE = 'test_plugin.py:279:8: error: "Request" has no attribute "id"'
TEST_LINE_WITHOUT_COL = ('test_plugin.py:279: '
                         'error: "Request" has no attribute "id"')
TEST_LINE_WITHOUT_LINE = ('test_plugin.py: '
                          'error: "Request" has no attribute "id"')


@pytest.fixture
def workspace(tmpdir):
    """Return a workspace."""
    return Workspace(uris.from_fs_path(str(tmpdir)), Mock())


@pytest.fixture
def document(workspace):
    return Document(DOC_URI, workspace, DOC_TYPE_ERR)


class FakeConfig(object):
    def plugin_settings(self, plugin, document_path=None):
        return {}


def test_plugin(document):
    config = FakeConfig()
    workspace = None
    diags = plugin.pyls_lint(config, workspace, document, is_saved=False)

    assert len(diags) == 1
    diag = diags[0]
    assert diag['message'] == TYPE_ERR_MSG
    assert diag['range']['start'] == {'line': 0, 'character': 0}
    assert diag['range']['end'] == {'line': 0, 'character': 1}


def test_parse_full_line(document):
    diag = plugin.parse_line(TEST_LINE, document)
    assert diag['message'] == '"Request" has no attribute "id"'
    assert diag['range']['start'] == {'line': 278, 'character': 7}
    assert diag['range']['end'] == {'line': 278, 'character': 8}


def test_parse_line_without_col(document):
    diag = plugin.parse_line(TEST_LINE_WITHOUT_COL, document)
    assert diag['message'] == '"Request" has no attribute "id"'
    assert diag['range']['start'] == {'line': 278, 'character': 0}
    assert diag['range']['end'] == {'line': 278, 'character': 1}


def test_parse_line_without_line(document):
    diag = plugin.parse_line(TEST_LINE_WITHOUT_LINE, document)
    assert diag['message'] == '"Request" has no attribute "id"'
    assert diag['range']['start'] == {'line': 0, 'character': 0}
    assert diag['range']['end'] == {'line': 0, 'character': 1}


@pytest.mark.parametrize('word,bounds', [('', (7, 8)), ('my_var', (7, 13))])
def test_parse_line_with_context(monkeypatch, word, bounds, document):
    monkeypatch.setattr(Document, 'word_at_position', lambda *args: word)
    diag = plugin.parse_line(TEST_LINE, document)
    assert diag['message'] == '"Request" has no attribute "id"'
    assert diag['range']['start'] == {'line': 278, 'character': bounds[0]}
    assert diag['range']['end'] == {'line': 278, 'character': bounds[1]}
