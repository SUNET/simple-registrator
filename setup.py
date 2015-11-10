#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from distutils.core import setup
from os.path import abspath, dirname, join
from platform import python_implementation
from setuptools import find_packages
from sys import version_info

__author__ = 'Leif Johansson'
__version__ = '0.0.1'

here = abspath(dirname(__file__))
README = open(join(here, 'README.rst')).read()

install_requires = [
    'futures',
    'requests'
]

setup(name='registrator',
      version=__version__,
      description="Simple Registrator",
      long_description=README,
      classifiers=[
          # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      ],
      keywords='etcd docker',
      author=__author__,
      author_email='leifj@sunet.se',
      url='http://blogs.mnt.se',
      license='BSD',
      setup_requires=['nose>=1.0'],
      tests_require=['pbr==1.6', 'nose>=1.0', 'mock', 'testfixtures'],
      test_suite="nose.collector",
      packages=find_packages('src'),
      package_dir={'': 'src'},
      include_package_data=True,
      zip_safe=False,
      install_requires=install_requires,
      entry_points={
          'console_scripts': ['registrator=registrator:main']
      },
      message_extractors={'src': [
          ('**.py', 'python', None),
          ('**/templates/**.html', 'mako', None),
      ]},
)
