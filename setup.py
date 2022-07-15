"""
Py-Tree-Sitter-Type-Provider
"""

import os
from setuptools import setup


with open(os.path.join(os.path.dirname(__file__), "README.md")) as f:
    LONG_DESCRIPTION = f.read()

setup(
    name="tree_sitter_type_provider",
    version="2.1.0",
    maintainer="Wen Kokke",
    maintainer_email="me@wen.works",
    author="Wen Kokke",
    author_email="me@wen.works",
    url="https://github.com/wenkokke/py-tree-sitter-type-provider",
    license="MIT",
    platforms=["any"],
    python_requires=">=3.3",
    description="Type providers for tree-sitter in Python",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Topic :: Software Development :: Compilers",
        "Topic :: Text Processing :: Linguistic",
    ],
    packages=["tree_sitter_type_provider"],
    project_urls={"Source": "https://github.com/wenkokke/py-tree-sitter-type-provider"},
    install_requires=["tree_sitter", "dataclasses-json"],
)
