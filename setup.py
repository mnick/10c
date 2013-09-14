from setuptools import setup

setup(
    name='tenc',
    version='0.1',
    classifiers=[
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
    ],
    packages=['tenc', ],
    entry_points={
        'console_scripts': '10c = tenc.cli:main'
    },
    license='GPL v3',
    long_description=open('README.md').read(),
    author='Maximilian Nickel',
    author_email='nickel@dbs.ifi.lmu.de',
    use_2to3=True
)
