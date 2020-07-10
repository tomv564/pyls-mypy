# -*- coding: utf-8 -*-
"""
File that contains the pyls plugin mypy-ls.

Created on Fri Jul 10 09:53:57 2020

@author: Richard Kellnberger
"""
import re
import tempfile
import os
import os.path
import logging
from mypy import api as mypy_api
from pyls import hookimpl
from pyls.workspace import Document, Workspace
from pyls.config.config import Config
from typing import Optional, Dict, Any, IO, List
import atexit

line_pattern: str = r"((?:^[a-z]:)?[^:]+):(?:(\d+):)?(?:(\d+):)? (\w+): (.*)"

log = logging.getLogger(__name__)

mypyConfigFile: Optional[str] = None

tmpFile: Optional[IO[str]] = None


def parse_line(line: str, document: Optional[Document] = None) -> Optional[Dict[str, Any]]:
    """
    Return a language-server diagnostic from a line of the Mypy error report.

    optionally, use the whole document to provide more context on it.


    Parameters
    ----------
    line : str
        Line of mypy output to be analysed.
    document : Optional[Document], optional
        Document in wich the line is found. The default is None.

    Returns
    -------
    Optional[Dict[str, Any]]
        The dict with the lint data.

    """
    result = re.match(line_pattern, line)
    if result:
        file_path, linenoStr, offsetStr, severity, msg = result.groups()

        if file_path != "<string>":  # live mode
            # results from other files can be included, but we cannot return
            # them.
            if document and document.path and not document.path.endswith(
                    file_path):
                log.warning("discarding result for %s against %s", file_path,
                            document.path)
                return None

        lineno = int(linenoStr or 1) - 1  # 0-based line number
        offset = int(offsetStr or 1) - 1  # 0-based offset
        errno = 2
        if severity == 'error':
            errno = 1
        diag: Dict[str, Any] = {
            'source': 'mypy',
            'range': {
                'start': {'line': lineno, 'character': offset},
                # There may be a better solution, but mypy does not provide end
                'end': {'line': lineno, 'character': offset + 1}
            },
            'message': msg,
            'severity': errno
        }
        if document:
            # although mypy does not provide the end of the affected range, we
            # can make a good guess by highlighting the word that Mypy flagged
            word = document.word_at_position(diag['range']['start'])
            if word:
                diag['range']['end']['character'] = (
                    diag['range']['start']['character'] + len(word))

        return diag
    return None


@hookimpl
def pyls_lint(config: Config, workspace: Workspace, document: Document,
              is_saved: bool) -> List[Dict[str, Any]]:
    """
    Lints.

    Parameters
    ----------
    config : Config
        The pyls config.
    workspace : Workspace
        The pyls workspace.
    document : Document
        The document to be linted.
    is_saved : bool
        Weather the document is saved.

    Returns
    -------
    List[Dict[str, Any]]
        List of the linting data.

    """
    settings = config.plugin_settings('mypy-ls')
    live_mode = settings.get('live_mode', True)
    args = ['--incremental',
            '--show-column-numbers',
            '--follow-imports', 'silent']

    global tmpFile
    if live_mode and not is_saved and tmpFile:
        tmpFile = open(tmpFile.name, "w")
        tmpFile.write(document.source)
        tmpFile.close()
        args.extend(['--shadow-file', document.path, tmpFile.name])
    elif not is_saved:
        return []

    if mypyConfigFile:
        args.append('--config-file')
        args.append(mypyConfigFile)
    args.append(document.path)
    if settings.get('strict', False):
        args.append('--strict')

    report, errors, _ = mypy_api.run(args)

    diagnostics = []
    for line in report.splitlines():
        diag = parse_line(line, document)
        if diag:
            diagnostics.append(diag)

    return diagnostics


@hookimpl
def pyls_settings(config: Config) -> Dict[str, Dict[str, Dict[str, str]]]:
    """
    Read the settings.

    Parameters
    ----------
    config : Config
        The pyls config.

    Returns
    -------
    Dict[str, Dict[str, Dict[str, str]]]
        The config dict.

    """
    configuration = init(config._root_path)
    return {"plugins": {"mypy-ls": configuration}}


def init(workspace: str) -> Dict[str, str]:
    """
    Find plugin and mypy config files and creates the temp file should it be used.

    Parameters
    ----------
    workspace : str
        The path to the current workspace.

    Returns
    -------
    Dict[str, str]
        The plugin config dict.

    """
    configuration = {}
    path = findConfigFile(workspace, "mypy-ls.cfg")
    if path:
        with open(path) as file:
            configuration = eval(file.read())
    global mypyConfigFile
    mypyConfigFile = findConfigFile(workspace, "mypy.ini")
    if (("enabled" not in configuration or configuration["enabled"])
       and ("live_mode" not in configuration or configuration["live_mode"])):
        global tmpFile
        tmpFile = tempfile.NamedTemporaryFile('w', delete=False)
        tmpFile.close()
    return configuration


def findConfigFile(path: str, name: str) -> Optional[str]:
    """
    Search for a config file.

    Search for a file of a given name from the directory specifyed by path through all parent
    directories. The first file found is selected.

    Parameters
    ----------
    path : str
        The path where the search starts.
    name : str
        The file to be found.

    Returns
    -------
    Optional[str]
        The path where the file has been found or None if no matching file has been found.

    """
    while True:
        p = f"{path}\\{name}"
        if os.path.isfile(p):
            return p
        else:
            loc = path.rfind("\\")
            if loc == -1:
                return None
            path = path[:loc]


@atexit.register
def close() -> None:
    """
    Deltes the tempFile should it exist.

    Returns
    -------
    None.

    """
    if tmpFile and tmpFile.name:
        os.unlink(tmpFile.name)
