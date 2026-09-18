import socket
import time

import pytest
from pytest_localserver.http import ContentServer


@pytest.fixture()
def otelserver(request):
    config = getattr(request, 'param', {})
    server = ContentServer(**config)
    server.start()
    wait_for_http_server(server)

    yield server

    server.stop()


@pytest.fixture(autouse=True)
def reset_pyramid_otelapm_state():
    """Reset module-level instrumentation state between tests.

    OpenTelemetry instrumentors, the global ``TracerProvider`` and
    pyramid_otelapm's own idempotency guard are all process-global, so
    tests that (de-)instrument need a clean slate.
    """
    import pyramid_otelapm

    yield

    pyramid_otelapm._instrumented = False

    for instrumentor_cls in _optional_instrumentor_classes():
        instrumentor = instrumentor_cls()
        if instrumentor.is_instrumented_by_opentelemetry:
            instrumentor.uninstrument()

    from opentelemetry.instrumentation.pyramid import PyramidInstrumentor

    pyramid_instrumentor = PyramidInstrumentor()
    if pyramid_instrumentor.is_instrumented_by_opentelemetry:
        pyramid_instrumentor.uninstrument()

    # The OpenTelemetry API only allows setting the global TracerProvider
    # once ("first one wins"). Reset the private module state so the next
    # test can install its own provider/exporter again.
    import opentelemetry.trace as _trace

    provider = _trace._TRACER_PROVIDER
    if provider is not None and hasattr(provider, "shutdown"):
        provider.shutdown()
    _trace._TRACER_PROVIDER_SET_ONCE._done = False
    _trace._TRACER_PROVIDER = None


def _optional_instrumentor_classes():
    classes = []
    try:
        from opentelemetry.instrumentation.requests import (
            RequestsInstrumentor,
        )

        classes.append(RequestsInstrumentor)
    except ImportError:
        pass
    try:
        from opentelemetry.instrumentation.botocore import (
            BotocoreInstrumentor,
        )

        classes.append(BotocoreInstrumentor)
    except ImportError:
        pass
    try:
        from opentelemetry.instrumentation.sqlalchemy import (
            SQLAlchemyInstrumentor,
        )

        classes.append(SQLAlchemyInstrumentor)
    except ImportError:
        pass
    try:
        from opentelemetry.instrumentation.logging import (
            LoggingInstrumentor,
        )

        classes.append(LoggingInstrumentor)
    except ImportError:
        pass
    return classes


def wait_for_http_server(httpserver, timeout=30):
    start_time = time.time()
    while True:
        try:
            sock = socket.create_connection(
                httpserver.server_address, timeout=0.1
            )
            sock.close()
            break
        except socket.error:
            if time.time() - start_time > timeout:
                raise TimeoutError()
