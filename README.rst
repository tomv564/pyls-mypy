Mypy plugin for PYLS
======================

.. image:: https://badge.fury.io/py/pyls-mypy.svg
    :target: https://badge.fury.io/py/pyls-mypy

.. image:: https://travis-ci.org/tomv564/pyls-mypy.svg?branch=master
    :target: https://travis-ci.org/tomv564/pyls-mypy

This is a plugin for the Palantir's Python Language Server (https://github.com/palantir/python-language-server)

It, like mypy, requires Python 3.2 or newer.


Installation
------------

Install into the same virtualenv as pyls itself.

``pip install pyls-mypy``

Configuration
-------------

``live_mode`` (default is True) provides type checking as you type.

As mypy is unaware of what file path is being checked, there are limitations with live_mode
 - Imports cannot be followed correctly
 - Stub files are not validated correctly

Turning off live_mode means you must save your changes for mypy diagnostics to update correctly.

``config_files`` (default is []) specifies a list of mypy configuration files.

This passes the first configuration file found in the list of provided files to mypy.
If the file path is relative, the file will be searched for all the way up to the root of the project directory.

File paths support user directory and environment variable expansion.

Depending on your editor, the configuration should be roughly like this:

::

    "pyls":
    {
        "plugins":
        {
            "pyls_mypy":
            {
                "enabled": true,
                "live_mode": false,
                "config_files": ["config/mypy.ini"]
            }
        }
    }
