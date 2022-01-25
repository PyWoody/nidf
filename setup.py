   
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


long_description = """
afind is a simple, striped down `find` replacement for use on NAS or slow disk drives. Results will be may be faster to `find` on SSDs for deep but not shallow searches.'
"""


setup(name="afind",
      description="aFind",
      long_description=long_description,
      license="BSD",
      version="0.0.1",
      author="Samuel Woodward",
      author_email="sam@woodward.fyi",
      maintainer="Samuel Woodward   ",
      maintainer_email="sam@woodward.fyi",
      url="https://github.com/PyWood/afind",
      packages=['afind'],
      python_requires='>= 3.7',
      classifiers=[
          'Programming Language :: Python :: 3',
      ])

