"""
Simple setup for message extractor
"""
from setuptools import setup, find_packages

setup(
    name="message-extractor",
    version="1.0.0",
    description="Extract messages from iMessage, WhatsApp, Gmail, and Google Calendar",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "google-auth==2.23.3",
        "google-auth-oauthlib==1.1.0",
        "google-auth-httplib2==0.1.1",
        "google-api-python-client==2.100.0",
        "python-dateutil==2.8.2",
    ],
)
