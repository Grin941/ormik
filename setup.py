from setuptools import setup, find_packages

__version__ = '0.1.0'


setup(
    name='ormik',
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    version=__version__,

    description='One more ORM implementation.',
    url='https://github.com/Grin941/ormik',
    licence='MIT',
    author='Grinenko Alexander',
    author_email='labamifi@gmail.com',
    classifiers=[
        'Development Status :: 1 - Planning',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: MacOS',
        'Operating System :: POSIX :: Linux',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Utilities',
    ],
    entry_points={
        # Run test ORM project
        'console_scripts': ['orm=bin.orm:main']
    },
)
