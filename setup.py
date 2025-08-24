"""
Setup configuration for EldersVR CLI
"""

from setuptools import setup, find_packages
import os

# Read README if it exists
readme_content = ""
if os.path.exists("README.md"):
    with open("README.md", "r", encoding="utf-8") as fh:
        readme_content = fh.read()

# Read requirements
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="eldersvr-cli",
    version="1.0.0",
    author="Indra Gunanda",
    author_email="info@ciptadusa.com",
    description="EldersVR ADB Onboarding CLI Tool",
    long_description=readme_content,
    long_description_content_type="text/markdown",
    url="https://github.com/EldersVR/eldersvr-cli",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: System :: Systems Administration",
        "Topic :: Utilities",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "eldersvr-onboard=eldersvr_cli.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "eldersvr_cli": [
            "config/*.json",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/EldersVR/eldersvr-cli/issues",
        "Source": "https://github.com/EldersVR/eldersvr-cli",
    },
)