#!/usr/bin/env python3
"""Setup script for supernova package."""

from setuptools import setup, find_packages

# Read the version from pyproject.toml
version = "1.0.0rc1"

setup(
    name="supernova",
    version=version,
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "supernova=supernova.cli.main:cli",
        ],
    },
) 