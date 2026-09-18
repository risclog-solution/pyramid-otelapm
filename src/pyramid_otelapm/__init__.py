"""OpenTelemetry APM integration for the Pyramid framework.

This package is a drop-in, vendor-neutral replacement for
``pyramid_elasticapm``: it sets up the OpenTelemetry SDK, exports traces via
OTLP/HTTP and instruments a Pyramid application (plus a few commonly used
libraries) with as little wiring as possible.

Usage
=====

Include it in your Pyramid application via config::

    [app:main]
    ...
    pyramid.includes = pyramid_otelapm

or programmatically::

    config.include('pyramid_otelapm')

Settings
========

Settings for the OpenTelemetry SDK are specified via the ``opentelemetry``
namespace:

* ``opentelemetry.endpoint``: The OTLP/HTTP collector endpoint, e.g.
  ``http://otel-collector.example.com:4318``. If unset, ``pyramid_otelapm``
  stays completely inactive (no-op).
* ``opentelemetry.service_name``: The service name reported to the
  collector.
* ``opentelemetry.environment``: The deployment environment (e.g. testing,
  production, …), reported as ``deployment.environment``.
* ``opentelemetry.service_distribution``: The name of the package you are
  deploying. ``pyramid_otelapm`` will retrieve the installed version of this
  package and report it as ``service.version``.
* ``opentelemetry.transactions_ignore_patterns``: Whitespace separated list
  of regular expressions; matching request URLs are excluded from tracing.

Instrumented libraries
=======================

Besides the Pyramid request/response cycle itself, ``pyramid_otelapm``
enables the following (optional, best-effort) OpenTelemetry
instrumentations if the respective libraries are installed:

* ``requests`` (outgoing HTTP calls)
* ``botocore`` (boto3/AWS calls, e.g. S3)
* ``SQLAlchemy`` (database queries)
* ``logging`` (correlate log records with the active trace/span)
"""

import importlib.metadata
import logging
import os

log = logging.getLogger(__name__)

_instrumented = False

#: Name of the environment variable read (once, at import time) by
#: ``opentelemetry-instrumentation-pyramid`` to exclude matching URLs from
#: tracing.
EXCLUDED_URLS_ENV_VAR = "OTEL_PYTHON_PYRAMID_EXCLUDED_URLS"


def includeme(config):
    """Pyramid entry point, activated via ``config.include('pyramid_otelapm')``.

    No-op if ``opentelemetry.endpoint`` is not configured.
    """
    settings = config.registry.settings
    if not settings.get("opentelemetry.endpoint"):
        return

    setup_tracing(settings)
    _configure_excluded_urls(settings)

    from opentelemetry.instrumentation.pyramid import PyramidInstrumentor

    PyramidInstrumentor().instrument_config(config)


def setup_tracing(settings):
    """Set up the global OpenTelemetry SDK and generic instrumentations.

    This is called automatically by :func:`includeme`, but can also be
    called directly and as early as possible during application startup --
    before any SQLAlchemy engines, ``requests`` calls or ``boto3``/S3
    clients are created -- so the respective instrumentations can patch
    them. Calling it again later (e.g. implicitly via ``config.include``)
    is a safe no-op.

    Returns the active ``TracerProvider``, or ``None`` if OpenTelemetry is
    disabled (no ``opentelemetry.endpoint`` configured).
    """
    global _instrumented

    endpoint = settings.get("opentelemetry.endpoint")
    if not endpoint:
        return None

    from opentelemetry import trace

    if _instrumented:
        return trace.get_tracer_provider()

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    service_name = settings.get("opentelemetry.service_name", "pyramid")
    environment = settings.get("opentelemetry.environment", "production")

    # The distributed package whose installed version is reported as the
    # service version, so APM/RUM events can be tied back to the exact
    # software release they were logged from.
    service_distribution = settings.get("opentelemetry.service_distribution")
    service_version = "unknown"
    if service_distribution:
        try:
            service_version = importlib.metadata.version(
                service_distribution
            )
        except importlib.metadata.PackageNotFoundError:
            pass

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": service_version,
            "deployment.environment": environment,
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(
        endpoint=f"{endpoint.rstrip('/')}/v1/traces",
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _instrument_optional_libraries()

    _instrumented = True
    log.info("OpenTelemetry tracing enabled, exporting to %s", endpoint)
    return provider


def _instrument_optional_libraries():
    """Instrument commonly used libraries, if installed.

    These are generic, framework independent instrumentations. They are
    safe to enable globally since they patch the respective libraries
    once, regardless of how many engines/clients are created afterwards.
    """
    try:
        from opentelemetry.instrumentation.requests import (
            RequestsInstrumentor,
        )
    except ImportError:
        pass
    else:
        RequestsInstrumentor().instrument()

    try:
        from opentelemetry.instrumentation.botocore import (
            BotocoreInstrumentor,
        )
    except ImportError:
        pass
    else:
        BotocoreInstrumentor().instrument()

    try:
        from opentelemetry.instrumentation.sqlalchemy import (
            SQLAlchemyInstrumentor,
        )
    except ImportError:
        pass
    else:
        SQLAlchemyInstrumentor().instrument()

    try:
        from opentelemetry.instrumentation.logging import (
            LoggingInstrumentor,
        )
    except ImportError:
        pass
    else:
        LoggingInstrumentor().instrument(set_logging_format=False)


def _configure_excluded_urls(settings):
    """Translate ``opentelemetry.transactions_ignore_patterns`` into the
    env var the Pyramid instrumentation reads to exclude matching URLs
    from tracing.

    Must run before ``opentelemetry.instrumentation.pyramid`` is imported
    for the first time, since it reads the env var once at import time.
    """
    patterns = settings.get(
        "opentelemetry.transactions_ignore_patterns", ""
    ).split()
    if not patterns:
        return
    existing = os.environ.get(EXCLUDED_URLS_ENV_VAR, "")
    combined = ",".join(filter(None, [existing, *patterns]))
    os.environ[EXCLUDED_URLS_ENV_VAR] = combined


def get_transaction_name(request):
    """Build a human readable transaction/view name for a request.

    Mirrors ``pyramid_elasticapm.TweenFactory.get_transaction_name``.
    Useful e.g. to pass a consistent transaction name to a frontend RUM
    agent alongside the backend traces.
    """
    transaction_name = request.path
    if request.matched_route:
        transaction_name = request.matched_route.pattern
    elif hasattr(request, "view_name"):
        transaction_name = request.view_name
    if transaction_name.startswith("/fanstatic") or (
        transaction_name == "/favicon.ico"
    ):
        transaction_name = "resources/*subpath"
    if not transaction_name:
        return ""
    return f"{request.method} {transaction_name}"
