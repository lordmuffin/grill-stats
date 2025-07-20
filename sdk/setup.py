"""
Setup script for the Grill Stats API Client SDK.
"""

from setuptools import find_packages, setup

# Read the version from the package
version: dict = {}
with open("grill_stats_client/__init__.py") as fp:
    for line in fp:
        if line.startswith("__version__"):
            exec(line, version)
            break

# Read the README.md file
with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="grill_stats_client",
    version=version.get("__version__", "0.1.0"),
    description="Grill Stats API Client SDK",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Grill Stats Team",
    author_email="info@grillstats.example.com",
    url="https://github.com/lordmuffin/grill-stats",
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.0",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
)
