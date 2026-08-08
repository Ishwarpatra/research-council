#!/usr/bin/env python3
"""
Research Consensus Council (RCC) — Setuptools Setup Script
Standard non-interactive setup script for pip installation and package builds.
"""

from setuptools import find_packages, setup

setup(
    name="research-council",
    version="1.0.0",
    description="Multi-agent research consensus council with persistence & REST API dashboard.",
    py_modules=["api", "council", "circuit", "config", "db"],
    packages=find_packages(),
)
