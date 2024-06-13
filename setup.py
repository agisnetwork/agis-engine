# -*- coding:utf-8 -*-
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="PyAgentlayer",
    version="0.2.2",
    author="Metatrust Labs",
    description="python sdk for agentlayer",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MetaTrustLabs/AgentLayerSDK",
    packages=find_packages("src"),
    package_dir={"": "src"},
    package_data={'': ['abi/*']},
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=[
        "web3>=6.0.0",
        "Flask>=3.0.2",
        "requests>=2.31.0",
        "python-dotenv>=1.0.1",
        "pydantic>=2.6.4"
    ],
    extras_require={},
    license="AGPL-3.0",
)
