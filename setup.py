from setuptools import setup, find_packages

with open("README.md", "r") as f:
    readme = f.read()

setup(
    name='analytoolz',
    version='0.3.0',
    author='Mak Shimizu',
    author_email='mak@fish.razor.jp',
    description='Utilities for Google Analytics and Google Cloud Platform.',
    long_description=readme,
    long_description_content_type='ext/markdown',
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Topic :: Internet",
    ],
)
