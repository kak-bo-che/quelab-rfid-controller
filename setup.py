#!/usr/bin/env python

from distutils.core import setup

setup(name='quelabrfid',
      version='1.0',
      description='A Control Program for the Quelab RFID Door Controller',
      author='Troy Ross',
      author_email='kak.bo.che@gmail.com',
      url='https://github.com/kak-bo-che/quelab-rfid-controller',
      packages=['quelabrfid'],
      scripts=['scripts/rfidreader']
     )