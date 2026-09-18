# Copyright (c) 2026 riscLOG Solution GmbH
# See also LICENSE
"""OpenTelemetry APM integration for the Pyramid framework
"""

import os.path

from setuptools import find_packages, setup

setup(
    name='pyramid-otelapm',
    version='0.1.0.dev0',
    python_requires='>=3.11',
    install_requires=[
        'opentelemetry-api',
        'opentelemetry-exporter-otlp-proto-http',
        'opentelemetry-instrumentation-pyramid',
        'opentelemetry-sdk',
        'pyramid',
    ],
    extras_require={
        'requests': ['opentelemetry-instrumentation-requests'],
        'botocore': ['opentelemetry-instrumentation-botocore'],
        'sqlalchemy': ['opentelemetry-instrumentation-sqlalchemy'],
        'logging': ['opentelemetry-instrumentation-logging'],
        'test': [
            'pytest',
            'pytest-cache',
            'pytest-cov',
            'pytest-rerunfailures',
            'pytest-sugar',
            'webtest',
            'pytest_localserver',
            'opentelemetry-instrumentation-requests',
            'opentelemetry-instrumentation-botocore',
            'opentelemetry-instrumentation-sqlalchemy',
            'opentelemetry-instrumentation-logging',
            'sqlalchemy',
            'boto3',
        ],
    },
    author='Sebastian Wehrmann (riscLOG Solution GmbH)',
    author_email='sebastian@risclog.com',
    license='BSD',
    url='https://github.com/risclog-solution/pyramid-otelapm',
    keywords='opentelemetry otel apm pyramid',
    classifiers="""\
License :: OSI Approved :: BSD License
Programming Language :: Python
Programming Language :: Python :: 3
Programming Language :: Python :: 3.11
Programming Language :: Python :: 3.12
Programming Language :: Python :: 3 :: Only
"""[
        :-1
    ].split(
        '\n'
    ),
    description=__doc__.strip(),
    long_description=(
        '.. contents::\n\n'
        + open(os.path.join('README.rst')).read()
        + '\n\n'
        + open('CHANGES.rst').read()
    ),
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    zip_safe=False,
)
