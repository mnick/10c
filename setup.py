from setuptools import setup

setup(
    name='tenc',
    version='0.2',
    classifiers=[
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3'
    ],
    package_dir={'tenc': 'tenc'},
    packages=['tenc'],
    entry_points={'console_scripts': '10c = tenc.cli:main'},
    license='GPLv3',
    long_description=open('README.md', 'rb').read(),
    author='Maximilian Nickel',
    author_email='mnick@mit.edu',
    use2to3=True
)
