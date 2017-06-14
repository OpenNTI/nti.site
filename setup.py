import codecs
from setuptools import setup, find_packages


TESTS_REQUIRE = [
    'fudge',
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
    version=_read('version.txt').strip(),
    author='Jason Madden',
    author_email='jason@nextthought.com',
    description="Opinionated ZODB persistent site implementations",
    long_description=_read('README.rst'),
    url="https://github.com/NextThought/nti.site",
    license='Apache',
    keywords='Site management',
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
    zip_safe=True,
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    namespace_packages=['nti'],
    tests_require=TESTS_REQUIRE,
    install_requires=[
        'BTrees >= 4.3.2', # permissive get()
        'ZODB',
        'nti.schema',
        'nti.transactions',
        'persistent',
        'setuptools',
        'six',
        'transaction >= 2.1.1', # for looser text/byte handling
        'zope.component',
        'zope.container',
        'zope.interface >= 4.4.2',
        'zope.location',
        'zope.proxy',
        'zope.site',
        'zope.traversing',
    ],
    extras_require={
        'test': TESTS_REQUIRE,
    },
)
