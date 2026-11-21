from setuptools import setup, find_packages

setup(
    name="auto-review",
    version="0.1.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "auto-review=auto_review.cli:main",
        ],
    },
)
