import codecs
from setuptools import setup, find_packages

version = '0.0.0'

entry_points = {
    'console_scripts': [
    ],
}

TESTS_REQUIRE = [
    'fudge',
    'nose2[coverage_plugin]',
    'nti.testing',
    'pyhamcrest',
    'z3c.baseregistry',
    'zope.testrunner',
]

def _read(fname):
    with codecs.open(fname, encoding='utf-8') as f:
        return f.read()

setup(
    name='nti.site',
    version=version,
    author='Jason Madden',
    author_email='jason@nextthought.com',
    description="NTI Site",
    long_description=_read('README.rst'),
    license='Apache',
    keywords='Site management',
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: CPython'
        'Programming Language :: Python :: Implementation :: PyPy'
    ],
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    namespace_packages=['nti'],
    tests_require=TESTS_REQUIRE,
    install_requires=[
        'setuptools',
        'persistent',
        'six',
        'ZODB',
        'zope.component',
        'zope.container',
        'zope.interface',
        'zope.location',
        'zope.proxy',
        'zope.site',
        'zope.traversing',
        'nti.schema',
        'nti.transactions'
    ],
    extras_require={
        'test': TESTS_REQUIRE,
    },
    entry_points=entry_points
)
