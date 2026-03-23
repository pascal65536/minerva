from setuptools import setup, find_packages

setup(
    name="minerva-plugin",
    version="1.0.0",
    description="Minerva - Flake8 plugin",
    author="pascal65536",
    author_email="pascal65536@gmail.com",
    packages=find_packages(),
    entry_points={
        "flake8.extension": [
            "MN = minerva_plugin:Minerva",
        ],
    },
    install_requires=[
        "flake8>=3.8.0",
    ],
    python_requires=">=3.8",
    classifiers=[
        "Framework :: Flake8",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
    ],
)