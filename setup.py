from setuptools import find_packages, setup

setup(
    author="rr-",
    author_email="rr-@sakuya.pl",
    name="tenff",
    long_description="A certain typing contest site spin-off in CLI",
    packages=find_packages(),
    entry_points={"console_scripts": ["10ff = tenff.__main__:main"]},
    package_dir={"tenff": "tenff"},
    package_data={"tenff": ["data/*.*"]},
)
