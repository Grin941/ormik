from setuptools import setup, find_packages
from setuptools.command.install import install as _install

__version__ = '0.4.0'


class NLTKInstall(_install):
    def run(self):
        _install.do_egg_install(self)

        import nltk
        nltk.download('averaged_perceptron_tagger')


setup(
    cmdclass={'install': NLTKInstall},
    name='Code base analizer',
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    version=__version__,
    install_requires=['nltk'],
    setup_requires=['nltk'],

    description='Module displays most popular words found in your codebase.',
    url='https://github.com/Grin941/codebase_analizer',
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
        'console_scripts': ['analize_codebase=bin.analize_codebase:main']
    },
)
