from setuptools import setup, find_packages
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(name="observicia",
      version="0.1.9",
      description="Cloud Native Observability SDK for LLM applications",
      long_description=long_description,
      long_description_content_type="text/markdown",
      url="https://github.com/observicia/observicia",
      packages=find_packages(where="sdk"),
      package_dir={"": "sdk"},
      python_requires=">=3.8",
      install_requires=[
          "numpy>=1.26.0", "requests>=2.32.3", "tiktoken>=0.7.0",
          "opentelemetry-api>=1.22.0", "opentelemetry-sdk>=1.22.0",
          "opentelemetry-exporter-otlp>=1.22.0",
          "opentelemetry-instrumentation>=0.43b0", "openai>=1.55.3",
          "pyyaml>=6.0", "redis>=5.2.0"
      ],
      classifiers=[
          "Development Status :: 4 - Beta",
          "Intended Audience :: Developers",
          "License :: OSI Approved :: Apache Software License",
          "Operating System :: OS Independent",
          "Programming Language :: Python :: 3",
          "Programming Language :: Python :: 3.8",
          "Programming Language :: Python :: 3.9",
          "Programming Language :: Python :: 3.10",
          "Programming Language :: Python :: 3.11",
          "Topic :: Software Development :: Libraries :: Python Modules",
          "Topic :: System :: Monitoring",
          "Topic :: Scientific/Engineering :: Artificial Intelligence",
      ],
      keywords="llm, observability, monitoring, tracing, opentelemetry, opa",
      platforms=["any"],
      project_urls={
          "Documentation": "https://observicia.readthedocs.io/",
          "Bug Reports": "https://github.com/observicia/observicia/issues",
          "Source": "https://github.com/observicia/observicia",
          "Discussion": "https://github.com/observicia/observicia/discussions",
      })
