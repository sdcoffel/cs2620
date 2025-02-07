#this installs the entire project as a package
from setuptools import setup, find_packages

setup(
    name='design exercise 1',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        # external libraries go here
        'bcrypt',
    ],
)