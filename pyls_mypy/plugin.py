import re
import logging
import tempfile
import platform
import os
import contextlib
from pathlib import Path
from mypy import api as mypy_api
from pyls import hookimpl
from typing import IO, Tuple, Optional

line_pattern = r"([^:]+):(?:(\d+):)?(?:(\d+):)? (\w+): (.*)"

log = logging.getLogger(__name__)


def parse_line(line, document=None):
    '''
    Return a language-server diagnostic from a line of the Mypy error report;
    optionally, use the whole document to provide more context on it.
    '''
    result = re.match(line_pattern, line)
    if result:
        file_path, lineno, offset, severity, msg = result.groups()

        if file_path != "<string>":  # live mode
            # results from other files can be included, but we cannot return
            # them.
            if document and document.path and not document.path.endswith(
                    file_path):
                log.warning("discarding result for %s against %s", file_path,
                            document.path)
                return None

        lineno = int(lineno or 1) - 1  # 0-based line number
        offset = int(offset or 1) - 1  # 0-based offset
        errno = 2
        if severity == 'error':
            errno = 1
        diag = {
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


def smart_tempfile(settings) -> Optional[Tuple[IO[bytes], Path]]:
    """
    Returns a temporary file-like object opened in write mode and pointed to by
    the returned path.
    May fail if the configuration does not allow writing to disk.
    """
    if platform.system() == "Linux":
        p = Path("/proc") / str(os.getpid()) / "fd"
        if p.exists():
            try:
                import memfd
                fd = memfd.open("_", flags=0, mode="wb")
                return fd, p / str(fd.fileno())
            except IOError:
                pass # fallback
    if not settings.get("temporary_write", False):
        return None
    fd = tempfile.NamedTemporaryFile('wb')
    return (fd, fd.name)



@hookimpl
def pyls_lint(config, workspace, document, is_saved):
    settings = config.plugin_settings('pyls_mypy')
    live_mode = settings.get('live_mode', True)
    fd = contextlib.nullcontext(None)
    if live_mode:
        args = ['--incremental',
                '--show-column-numbers',
                '--follow-imports', 'silent']
        t  = smart_tempfile(settings)
        if t is None:
            args += ['--command', document.source]
        else:
            (fd, path) = t
            fd.write(document.source.encode("utf8"))
            fd.flush()
            args += ['--shadow-file', document.path, str(path), document.path]
    elif is_saved:
        args = ['--incremental',
                '--show-column-numbers',
                '--follow-imports', 'silent',
                document.path]
    else:
        return []

    if settings.get('strict', False):
        args.append('--strict')

    with fd:
        report, errors, _ = mypy_api.run(args)

    diagnostics = []
    for line in report.splitlines():
        diag = parse_line(line, document)
        if diag:
            diagnostics.append(diag)

    return diagnostics
