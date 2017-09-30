from setuptools import setup, find_packages


setup(
    author='rr-',
    author_email='rr-@sakuya.pl',
    name='10ff',
    long_description='A certain typing contest site spin-off in CLI',
    packages=find_packages(),
    entry_points={'console_scripts': ['10ff = 10ff.__main__:main']},
    package_dir={'10ff': '10ff'},
    package_data={'10ff': ['data/*.*']})

