from setuptools import setup, find_packages

setup(
    name="glance-ical-events",
    version="1.0.0",
    description="Flask API service for fetching and serving iCal events for Glance widgets",
    author="AWildLeon",
    url="https://github.com/AWildLeon/Glance-iCal-Events",
    # Include newly added service module
    py_modules=["app", "service"],
    install_requires=[
        "flask",
        "pytz>=2023.0", 
        "icalevents>=0.2.0",
        "gunicorn",
        # Explicit for service.py (even though icalevents pulls it indirectly)
        "python-dateutil>=2.8.2",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
)
