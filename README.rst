Mypy plugin for PYLS
======================

.. image:: https://badge.fury.io/py/mypy-ls.svg
    :target: https://badge.fury.io/py/mypy-ls

.. image:: https://github.com/Richardk2n/pyls-mypy/workflows/Python%20package/badge.svg?branch=master
    :target: https://github.com/Richardk2n/pyls-mypy/

This is a plugin for the `Python LSP Server`_.

.. _`Python LSP Server`: https://github.com/python-lsp/python-lsp-server

It, like mypy, requires Python 3.6 or newer.


Installation
------------

Install into the same virtualenv as python-lsp-server itself.

``pip install mypy-ls``

Configuration
-------------

``live_mode`` (default is True) provides type checking as you type. This writes to a tempfile every time a check is done.

Turning off ``live_mode`` means you must save your changes for mypy diagnostics to update correctly.

Depending on your editor, the configuration (found in a file called mypy-ls.cfg in your workspace or a parent directory) should be roughly like this:

::

    {
        "enabled": True,
        "live_mode": True,
        "strict": False
    }

Developing
-------------

Install development dependencies with (you might want to create a virtualenv first):

::

   pip install -r requirements.txt

The project is formatted with `black`_. You can either configure your IDE to automatically format code with it, run it manually (``black .``) or rely on pre-commit (see below) to format files on git commit.

This project uses `pre-commit`_ to enforce code-quality. After cloning the repository install the pre-commit hooks with:

::

   pre-commit install

After that pre-commit will run `all defined hooks`_ on every ``git commit`` and keep you from committing if there are any errors.

.. _black: https://github.com/psf/black
.. _rst-linter: https://github.com/Lucas-C/pre-commit-hooks-markup
.. _pre-commit: https://pre-commit.com/
.. _all defined hooks: .pre-commit-config.yaml
