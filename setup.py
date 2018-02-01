from os import path
from setuptools import setup

here = path.abspath(path.dirname(__file__))

# Try to convert markdown readme file to rst format
try:
    import pypandoc
    md_file = path.join(here, 'README.md')
    rst_file = path.join(here, 'README.rst')
    pypandoc.convert_file(source_file=md_file, outputfile=rst_file, to='rst')
except (ImportError, OSError, IOError, RuntimeError):
    pass

# Get the long description from the relevant file
with open(path.join(here, 'README.rst')) as f:
    long_description = f.read()


setup(
    name='youtrack',
    version='0.1.3',
    python_requires='>=2.6, <3',
    packages=['youtrack', 'youtrack.sync'],
    url='https://github.com/JetBrains/youtrack-rest-python-library',
    license='Apache 2.0',
    maintainer='Alexander Buturlinov',
    maintainer_email='imboot85@gmail.com',
    description='Python library for interacting with YouTrack via REST API',
    long_description=long_description,
    install_requires=[
        "httplib2 >= 0.7.4",
        # Cannot use original module because at the time it was modified in youtrack repo.
        # "urllib2_file",
        "six"
    ]
)
