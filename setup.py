#!/usr/bin/env python
from setuptools import setup
import versioneer


if __name__ == "__main__":
    setup(
        version=versioneer.get_version(),
        cmdclass=versioneer.get_cmdclass(),
        classifiers=[
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.6",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: 3.8",
        ],
        python_requires='>=3.6',
    )
