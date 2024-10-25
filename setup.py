import os
import setuptools

if os.path.exists('dist'):
  os.system('rm -r dist')

with open("README.md", "r") as fh:
  long_description = fh.read()

setuptools.setup(
  name="playplaysyn",
  version="0.0.2",
  author="92MING",
  author_email="contact@aiwife.io",
  description="This package provides a convenient interface (with runtime logic included) for accessing to PlayPlaySyn Ltd.'s AI-Character service. Hardware developers will only need to register proper interaction events(audio playing, emotion switch, etc) and the package will handle the rest.",
  long_description=long_description,
  long_description_content_type="text/markdown",
  url="https://github.com/92MING/playplaysyn",
  packages=setuptools.find_packages(),
  classifiers=[
  "Programming Language :: Python :: 3",
  "License :: OSI Approved :: MIT License",
  "Operating System :: OS Independent",
  ],
)