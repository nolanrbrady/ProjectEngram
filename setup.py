from pathlib import Path
from setuptools import setup

README = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")

setup(
    name='project-engram',
    version='1.0.0',
    description='Persistent memory CLI bridge for coding agents.',
    long_description=README,
    long_description_content_type='text/markdown',
    author='Project Engram',
    license='MIT',
    python_requires='>=3.8',
    py_modules=[
        'engram',
        'engram_config',
        'engram_lock',
        'engram_models',
        'engram_utils',
        'engram_storage',
        'engram_recall',
        'engram_commands',
    ],
    entry_points={
        'console_scripts': [
            'pmem=engram:main',
        ],
    },
    install_requires=[],
    classifiers=[
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Documentation',
    ],
)
