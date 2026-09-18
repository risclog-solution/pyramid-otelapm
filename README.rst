==================
pyramid-otelapm
==================

OpenTelemetry APM integration for the Pyramid framework.

This package is a drop-in, vendor-neutral replacement for
`pyramid-elasticapm <https://github.com/risclog-solution/pyramid-elasticapm>`_:
it sets up the OpenTelemetry SDK, exports traces via OTLP/HTTP and
instruments a Pyramid application (plus a few commonly used libraries) with
as little wiring as possible.


Installation
============

Install with pip::

    $ pip install pyramid-otelapm

Optionally, install support for instrumenting some commonly used
libraries::

    $ pip install pyramid-otelapm[requests,botocore,sqlalchemy,logging]

Then include it in your pyramid application via config::

    [app:main]
    ...
    pyramid.includes = pyramid_otelapm

or programmatically in your application::

    config.include('pyramid_otelapm')


Settings
========

Settings for the OpenTelemetry SDK can be specified via the
``opentelemetry`` namespace:

* ``opentelemetry.endpoint``: The OTLP/HTTP collector endpoint, e.g.
  ``http://otel-collector.example.com:4318``. If unset, ``pyramid_otelapm``
  stays completely inactive (no-op).
* ``opentelemetry.service_name``: The service name reported to the
  collector.
* ``opentelemetry.environment``: The deployment environment (e.g. testing,
  production, …), reported as ``deployment.environment``.
* ``opentelemetry.service_distribution``: The name of the package you are
  deploying. ``pyramid_otelapm`` will retrieve the installed version of
  this package and report it as ``service.version`` on every span, so
  traces can be tied back to the exact software release they were
  recorded from.
* ``opentelemetry.transactions_ignore_patterns``: Whitespace separated
  list of regular expressions; matching request URLs are excluded from
  tracing.


Instrumented libraries
=======================

Besides the Pyramid request/response cycle itself, ``pyramid_otelapm``
enables the following (optional, best-effort) OpenTelemetry
instrumentations if the respective libraries (and their corresponding
``opentelemetry-instrumentation-*`` package) are installed:

* ``requests`` (outgoing HTTP calls)
* ``botocore`` (boto3/AWS calls, e.g. S3)
* ``SQLAlchemy`` (database queries)
* ``logging`` (correlate log records with the active trace/span)

Missing optional instrumentation packages are silently skipped.


Instrumenting SQLAlchemy engines created before ``config.include``
====================================================================

``opentelemetry-instrumentation-sqlalchemy`` patches
``sqlalchemy.create_engine`` itself, so only engines created *after*
instrumentation was set up get traced. If your application creates
SQLAlchemy engines before the Pyramid ``Configurator`` is built (and
``config.include('pyramid_otelapm')`` is called), call
``pyramid_otelapm.setup_tracing(settings)`` explicitly, as early as
possible during application startup::

    import pyramid_otelapm

    pyramid_otelapm.setup_tracing(settings)
    # ... create SQLAlchemy engines, boto3 clients, etc ...

    config = Configurator(settings=settings)
    config.include('pyramid_otelapm')  # safe to call again, is a no-op

``setup_tracing`` is idempotent, so calling it again later via
``config.include`` is safe.


Transaction naming
==================

``pyramid_otelapm.get_transaction_name(request)`` returns a human readable
transaction name (``"<method> <route pattern>"``), the same convention
used by ``pyramid_elasticapm``. This is useful e.g. to pass a consistent
transaction/view name to a frontend RUM agent (like Grafana Faro or Elastic
APM RUM) alongside the backend traces.
