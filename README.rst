Mypy plugin for PYLSP
======================

.. image:: https://badge.fury.io/py/pylsp-mypy.svg
    :target: https://badge.fury.io/py/pylsp-mypy

.. image:: https://github.com/python-lsp/pylsp-mypy/workflows/Python%20package/badge.svg?branch=master
    :target: https://github.com/python-lsp/pylsp-mypy/

This is a plugin for the `Python LSP Server`_.

.. _`Python LSP Server`: https://github.com/python-lsp/python-lsp-server

It, like mypy, requires Python 3.7 or newer.


Installation
------------

Install into the same virtualenv as python-lsp-server itself.

``pip install pylsp-mypy``

Configuration
-------------

``live_mode`` (default is True) provides type checking as you type.
    This writes to a tempfile every time a check is done. Turning off ``live_mode`` means you must save your changes for mypy diagnostics to update correctly.

``dmypy`` (default is False) executes via ``dmypy run`` rather than ``mypy``.
    This uses the ``dmypy`` daemon and may dramatically improve the responsiveness of the ``pylsp`` server, however this currently does not work in ``live_mode``. Enabling this disables ``live_mode``, even for conflicting configs.

``strict`` (default is False) refers to the ``strict`` option of ``mypy``.
    This option often is too strict to be useful.

``overrides`` (default is ``[True]``) specifies a list of alternate or supplemental command-line options.
    This modifies the options passed to ``mypy`` or the mypy-specific ones passed to ``dmypy run``. When present, the special boolean member ``True`` is replaced with the command-line options that would've been passed had ``overrides`` not been specified. Later options take precedence, which allows for replacing or negating individual default options (see ``mypy.main:process_options`` and ``mypy --help | grep inverse``).

This project supports the use of ``pyproject.toml`` for configuration. It is in fact the preferred way. Using that your configuration could look like this:

::

    [tool.pylsp-mypy]
    enabled = true
    live_mode = true
    strict = true

A ``pyproject.toml`` does not conflict with the legacy config file given that it does not contain a ``pylsp-mypy`` section. The following explanation uses the syntax of the legacy config file. However, all these options also apply to the ``pyproject.toml`` configuration (note the lowercase bools).
Depending on your editor, the configuration (found in a file called pylsp-mypy.cfg in your workspace or a parent directory) should be roughly like this for a standard configuration:

::

    {
        "enabled": True,
        "live_mode": True,
        "strict": False
    }

With ``dmypy`` enabled your config should look like this:

::

    {
        "enabled": True,
        "live_mode": False,
        "dmypy": True,
        "strict": False
    }

With ``overrides`` specified (for example to tell mypy to use a different python than the currently active venv), your config could look like this:

::

    {
        "enabled": True,
        "overrides": ["--python-executable", "/home/me/bin/python", True]
    }


Developing
-------------

Install development dependencies with (you might want to create a virtualenv first):

::

   pip install -r requirements.txt

The project is formatted with `black`_. You can either configure your IDE to automatically format code with it, run it manually (``black .``) or rely on pre-commit (see below) to format files on git commit.

The project is formatted with `isort`_. You can either configure your IDE to automatically sort imports with it, run it manually (``isort .``) or rely on pre-commit (see below) to sort files on git commit.

The project uses two rst tests in order to assure uploadability to pypi: `rst-linter`_ as a pre-commit hook and `rstcheck`_ in a GitHub workflow. This does not catch all errors.

This project uses `pre-commit`_ to enforce code-quality. After cloning the repository install the pre-commit hooks with:

::

   pre-commit install

After that pre-commit will run `all defined hooks`_ on every ``git commit`` and keep you from committing if there are any errors.

.. _black: https://github.com/psf/black
.. _isort: https://github.com/PyCQA/isort
.. _rst-linter: https://github.com/Lucas-C/pre-commit-hooks-markup
.. _rstcheck: https://github.com/myint/rstcheck
.. _pre-commit: https://pre-commit.com/
.. _all defined hooks: .pre-commit-config.yaml
