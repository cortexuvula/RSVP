from setuptools import setup, find_packages

setup(
    name="rsvp-reader",
    version="1.0.0",
    description="Rapid Serial Visual Presentation (RSVP) speed reading application",
    author="RSVP Team",
    packages=find_packages(),
    install_requires=[
        "PyQt6>=6.4.0",
        "requests>=2.28.0",
        "beautifulsoup4>=4.11.0",
        "pyperclip>=1.8.0",
    ],
    entry_points={
        "console_scripts": [
            "rsvp=rsvp.main:main",
        ],
    },
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Education",
    ],
)
