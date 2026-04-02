"""
Backward-compatible setup.py for pip install.

The actual configuration is in pyproject.toml.
This file exists for editable installs: pip install -e .
"""
from setuptools import setup, find_packages

setup(
    package_dir={"seq_o_matic": "code"},
    packages=["seq_o_matic"] + [
        f"seq_o_matic.{pkg}" for pkg in find_packages(where="code")
    ],
    package_data={
        "seq_o_matic": [
            "config_file/*.json",
            "reagent_sequence_file/*.json",
            "reagent_sequence_file/**/*.json",
            "logo/*.png",
            "LOGO.png",
        ],
    },
)
