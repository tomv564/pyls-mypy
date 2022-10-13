# -*- coding: utf-8 -*-
"""
File that contains the python-lsp-server plugin pylsp-mypy.

Created on Fri Jul 10 09:53:57 2020

@author: Richard Kellnberger
"""
import ast
import atexit
import collections
import logging
import os
import os.path
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import IO, Any, Dict, List, Optional

import toml
from mypy import api as mypy_api
from pylsp import hookimpl
from pylsp.config.config import Config
from pylsp.workspace import Document, Workspace

line_pattern: str = r"((?:^[a-z]:)?[^:]+):(?:(\d+):)?(?:(\d+):)? (\w+): (.*)"

log = logging.getLogger(__name__)

# A mapping from workspace path to config file path
mypyConfigFileMap: Dict[str, Optional[str]] = {}

tmpFile: Optional[IO[str]] = None

# In non-live-mode the file contents aren't updated.
# Returning an empty diagnostic clears the diagnostic result,
# so store a cache of last diagnostics for each file a-la the pylint plugin,
# so we can return some potentially-stale diagnostics.
# https://github.com/python-lsp/python-lsp-server/blob/v1.0.1/pylsp/plugins/pylint_lint.py#L55-L62
last_diagnostics: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)

# Windows started opening opening a cmd-like window for every subprocess call
# This flag prevents that.
# This flag is new in python 3.7
# THis flag only exists on Windows
windows_flag: Dict[str, int] = (
    {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}  # type: ignore
)


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
            if document and document.path and not document.path.endswith(file_path):
                log.warning("discarding result for %s against %s", file_path, document.path)
                return None

        lineno = int(linenoStr or 1) - 1  # 0-based line number
        offset = int(offsetStr or 1) - 1  # 0-based offset
        errno = 2
        if severity == "error":
            errno = 1
        diag: Dict[str, Any] = {
            "source": "mypy",
            "range": {
                "start": {"line": lineno, "character": offset},
                # There may be a better solution, but mypy does not provide end
                "end": {"line": lineno, "character": offset + 1},
            },
            "message": msg,
            "severity": errno,
        }
        if document:
            # although mypy does not provide the end of the affected range, we
            # can make a good guess by highlighting the word that Mypy flagged
            word = document.word_at_position(diag["range"]["start"])
            if word:
                diag["range"]["end"]["character"] = diag["range"]["start"]["character"] + len(word)

        return diag
    return None


def apply_overrides(args: List[str], overrides: List[Any]) -> List[str]:
    """Replace or combine default command-line options with overrides."""
    overrides_iterator = iter(overrides)
    if True not in overrides_iterator:
        return overrides
    # If True is in the list, the if above leaves the iterator at the element after True,
    # therefore, the list below only contains the elements after the True
    rest = list(overrides_iterator)
    # slice of the True and the rest, add the args, add the rest
    return overrides[: -(len(rest) + 1)] + args + rest


def _get_settings(config: Config) -> Any:
    """
    Get settings checking for deprecated setting locations.

    Parameters
    ----------
    config : Config
        The pylsp config.

    Returns
    -------
    Dict[str, Any]
        Mypy settings to use.

    """
    settings = config.plugin_settings("pylsp_mypy")
    oldSettings1 = config.plugin_settings("mypy-ls")
    if oldSettings1 != {}:
        raise DeprecationWarning(
            "Your configuration uses the namespace mypy-ls, this should be changed to pylsp_mypy"
        )
    oldSettings2 = config.plugin_settings("mypy_ls")
    if oldSettings2 != {}:
        raise DeprecationWarning(
            "Your configuration uses the namespace mypy_ls, this should be changed to pylsp_mypy"
        )
    if settings == {}:
        settings = oldSettings1
        if settings == {}:
            settings = oldSettings2

    return settings


@hookimpl
def pylsp_lint(
    config: Config, workspace: Workspace, document: Document, is_saved: bool
) -> List[Dict[str, Any]]:
    """
    Lints.

    Parameters
    ----------
    config : Config
        The pylsp config.
    workspace : Workspace
        The pylsp workspace.
    document : Document
        The document to be linted.
    is_saved : bool
        Weather the document is saved.

    Returns
    -------
    List[Dict[str, Any]]
        List of the linting data.

    """
    settings = _get_settings(config)
    log.info(
        "lint settings = %s document.path = %s is_saved = %s",
        settings,
        document.path,
        is_saved,
    )

    live_mode = settings.get("live_mode", True)
    dmypy = settings.get("dmypy", False)

    if dmypy and live_mode:
        # dmypy can only be efficiently run on files that have been saved, see:
        # https://github.com/python/mypy/issues/9309
        log.warning("live_mode is not supported with dmypy, disabling")
        live_mode = False

    args = ["--show-column-numbers"]

    global tmpFile
    if live_mode and not is_saved:
        if tmpFile:
            tmpFile = open(tmpFile.name, "w")
        else:
            tmpFile = tempfile.NamedTemporaryFile("w", delete=False)
        log.info("live_mode tmpFile = %s", tmpFile.name)
        tmpFile.write(document.source)
        tmpFile.close()
        args.extend(["--shadow-file", document.path, tmpFile.name])
    elif not is_saved and document.path in last_diagnostics:
        # On-launch the document isn't marked as saved, so fall through and run
        # the diagnostics anyway even if the file contents may be out of date.
        log.info(
            "non-live, returning cached diagnostics len(cached) = %s",
            last_diagnostics[document.path],
        )
        return last_diagnostics[document.path]

    mypyConfigFile = mypyConfigFileMap.get(workspace.root_path)
    if mypyConfigFile:
        args.append("--config-file")
        args.append(mypyConfigFile)

    args.append(document.path)

    if settings.get("strict", False):
        args.append("--strict")

    overrides = settings.get("overrides", [True])
    exit_status = 0

    if not dmypy:
        args.extend(["--incremental", "--follow-imports", "silent"])
        args = apply_overrides(args, overrides)

        if shutil.which("mypy"):
            # mypy exists on path
            # -> use mypy on path
            log.info("executing mypy args = %s on path", args)
            completed_process = subprocess.run(
                ["mypy", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, **windows_flag
            )
            report = completed_process.stdout.decode()
            errors = completed_process.stderr.decode()
            exit_status = completed_process.returncode
        else:
            # mypy does not exist on path, but must exist in the env pylsp-mypy is installed in
            # -> use mypy via api
            log.info("executing mypy args = %s via api", args)
            report, errors, exit_status = mypy_api.run(args)
    else:
        # If dmypy daemon is non-responsive calls to run will block.
        # Check daemon status, if non-zero daemon is dead or hung.
        # If daemon is hung, kill will reset
        # If daemon is dead/absent, kill will no-op.
        # In either case, reset to fresh state

        if shutil.which("dmypy"):
            # dmypy exists on path
            # -> use mypy on path
            completed_process = subprocess.run(
                ["dmypy", *apply_overrides(args, overrides)], stderr=subprocess.PIPE, **windows_flag
            )
            errors = completed_process.stderr.decode()
            exit_status = completed_process.returncode
            if exit_status != 0:
                log.info(
                    "restarting dmypy from status: %s message: %s via path",
                    exit_status,
                    errors.strip(),
                )
                subprocess.run(["dmypy", "kill"], **windows_flag)
        else:
            # dmypy does not exist on path, but must exist in the env pylsp-mypy is installed in
            # -> use dmypy via api
            _, errors, exit_status = mypy_api.run_dmypy(["status"])
            if exit_status != 0:
                log.info(
                    "restarting dmypy from status: %s message: %s via api",
                    exit_status,
                    errors.strip(),
                )
                mypy_api.run_dmypy(["kill"])

        # run to use existing daemon or restart if required
        args = ["run", "--"] + apply_overrides(args, overrides)

        if shutil.which("dmypy"):
            # dmypy exists on path
            # -> use mypy on path
            log.info("dmypy run args = %s via path", args)
            completed_process = subprocess.run(
                ["dmypy", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, **windows_flag
            )
            report = completed_process.stdout.decode()
            errors = completed_process.stderr.decode()
            exit_status = completed_process.returncode
        else:
            # dmypy does not exist on path, but must exist in the env pylsp-mypy is installed in
            # -> use dmypy via api
            log.info("dmypy run args = %s via api", args)
            report, errors, exit_status = mypy_api.run_dmypy(args)

    log.debug("report:\n%s", report)
    log.debug("errors:\n%s", errors)

    diagnostics = []

    # Expose generic mypy error on the first line.
    if errors:
        diagnostics.append(
            {
                "source": "mypy",
                "range": {
                    "start": {"line": 0, "character": 0},
                    # Client is supposed to clip end column to line length.
                    "end": {"line": 0, "character": 1000},
                },
                "message": errors,
                "severity": 1 if exit_status != 0 else 2,  # Error if exited with error or warning.
            }
        )

    for line in report.splitlines():
        log.debug("parsing: line = %r", line)
        diag = parse_line(line, document)
        if diag:
            diagnostics.append(diag)

    log.info("pylsp-mypy len(diagnostics) = %s", len(diagnostics))

    last_diagnostics[document.path] = diagnostics
    return diagnostics


@hookimpl
def pylsp_settings(config: Config) -> Dict[str, Dict[str, Dict[str, str]]]:
    """
    Read the settings.

    Parameters
    ----------
    config : Config
        The pylsp config.

    Returns
    -------
    Dict[str, Dict[str, Dict[str, str]]]
        The config dict.

    """

    settings = _get_settings(config)
    log.info(
        "initialization settings = %s",
        settings,
    )

    config_names = settings.get("config_names", [])

    configuration = init(config._root_path, config_names)
    return {"plugins": {"pylsp_mypy": configuration}}


def init(workspace: str, config_names: List[str] = []) -> Dict[str, str]:
    """
    Find plugin and mypy config files and creates the temp file should it be used.

    Parameters
    ----------
    workspace : str
        The path to the current workspace.
    config_names : List[str]
        List of configuration file names that will be checked for first.

    Returns
    -------
    Dict[str, str]
        The plugin config dict.

    """
    log.info("init workspace = %s", workspace)

    configuration = {}
    path = findConfigFile(
        workspace, ["pylsp-mypy.cfg", "mypy-ls.cfg", "mypy_ls.cfg", "pyproject.toml"]
    )
    if path:
        if "pyproject.toml" in path:
            configuration = toml.load(path).get("tool").get("pylsp-mypy")
        else:
            with open(path) as file:
                configuration = ast.literal_eval(file.read())

    possibleNames = config_names + ["mypy.ini", ".mypy.ini", "pyproject.toml"]
    mypyConfigFile = findConfigFile(workspace, possibleNames)
    mypyConfigFileMap[workspace] = mypyConfigFile

    log.info("mypyConfigFile = %s configuration = %s", mypyConfigFile, configuration)
    return configuration


def findConfigFile(path: str, names: List[str]) -> Optional[str]:
    """
    Search for a config file.

    Search for a file of a given name from the directory specifyed by path through all parent
    directories. The first file found is selected.

    Parameters
    ----------
    path : str
        The path where the search starts.
    names : List[str]
        The file to be found (or alternative names).

    Returns
    -------
    Optional[str]
        The path where the file has been found or None if no matching file has been found.

    """
    start = Path(path).joinpath(names[0])  # the join causes the parents to include path
    for parent in start.parents:
        for name in names:
            file = parent.joinpath(name)
            if file.is_file():
                if file.name in ["mypy-ls.cfg", "mypy_ls.cfg"]:
                    raise DeprecationWarning(
                        f"{str(file)}: {file.name} is no longer supported, you should rename your "
                        "config file to pylsp-mypy.cfg or preferably use a pyproject.toml instead."
                    )
                if file.name == "pyproject.toml":
                    isPluginConfig = "pylsp-mypy.cfg" in names
                    configPresent = (
                        toml.load(file)
                        .get("tool", {})
                        .get("pylsp-mypy" if isPluginConfig else "mypy")
                        is not None
                    )
                    if not configPresent:
                        continue
                return str(file)

    return None


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
