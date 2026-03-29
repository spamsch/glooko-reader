from setuptools import setup, find_packages

setup(
    name="glooko-reader",
    version="0.1.0",
    description="Unofficial Python client for the Glooko diabetes data platform",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/spamsch/glooko-reader",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "requests",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
    ],
)
