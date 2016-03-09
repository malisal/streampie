from setuptools import setup

with open('requirements.txt') as f:
   required = f.read().splitlines()

setup(
   name = "streampie",
   py_modules = ["streampie"],
   version = '0.2.1',
   description = 'A simple, parallel stream processing library',
   author = 'Luka Malisa',
   author_email = 'luka.malisha@gmail.com',
   url = 'https://github.com/malisal/streampie',
   keywords = ['stream', 'parallel', 'distributed'],
   platforms=['any'],
   classifiers = [],
   install_requires = [
      "dill>=0.2.5",
      "redis>=2.10.5",
      "sphinx>=1.3.6",
      "ipython>=4.1.2",
      "matplotlib>=1.5.1",
   ]

)

