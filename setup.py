import codecs
from setuptools import setup, find_packages


TESTS_REQUIRE = [
    'fudge',
    'nti.testing >= 3.0.0',
    'pyhamcrest',
    'z3c.baseregistry',
    'zope.testrunner',
    'coverage',
    'zope.testing',
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
        'Development Status :: 5 - Production/Stable',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
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
        'BTrees >= 4.3.2',  # permissive get()
        # test dependencies have this at >= 5.6.0; for consistency,
        # do the same in regular deps.
        'ZODB >= 5.6.0',
        'nti.schema',
        'nti.transactions >= 4.0.0', # nti.transactions.loop
        'persistent',
        'setuptools',
        'six',
        'transaction >= 2.4.0',  # for looser text/byte handling
        'zope.component',
        'zope.container',
        'zope.interface >= 4.4.2',
        'zope.location',
        'zope.proxy',
        'zope.site >= 4.4.0', # Proper site cleanup.
        'zope.traversing',
    ],
    extras_require={
        'test': TESTS_REQUIRE,
        'docs': [
            'Sphinx',
            'repoze.sphinx.autointerface',
            'sphinx_rtd_theme',
        ] + TESTS_REQUIRE # To be able to import nti.site.testing
    },
)
