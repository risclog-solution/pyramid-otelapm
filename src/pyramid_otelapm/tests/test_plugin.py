import time

from pyramid.config import Configurator
from webtest import TestApp

import pyramid_otelapm


def make_app(endpoint, **extra_settings):
    settings = {
        'opentelemetry.endpoint': endpoint,
        'opentelemetry.service_name': 'pyramid-test-app',
        'opentelemetry.environment': 'testing',
        'opentelemetry.service_distribution': 'pytest',
        **extra_settings,
    }
    config = Configurator(settings=settings)
    config.include('pyramid_otelapm')

    config.add_route('index', '/')
    config.add_view(
        lambda x: {'status': 'ok'}, route_name='index', renderer='json'
    )
    config.add_route('ignored', '/mark_log')
    config.add_view(
        lambda x: {'status': 'ok'}, route_name='ignored', renderer='json'
    )

    return config.make_wsgi_app()


def get_spans(otelserver):
    # Give the exporter some time to flush spans to the otel collector.
    for _ in range(50):
        if otelserver.requests:
            break
        time.sleep(0.1)
    return otelserver.requests


def test_get(otelserver):
    assert [] == otelserver.requests

    app = TestApp(make_app(otelserver.url))

    resp = app.get('/')
    resp.mustcontain(b'{"status": "ok"}')

    requests = get_spans(otelserver)
    assert len(requests) != 0
    assert requests[0].url.endswith('/v1/traces')


def test_post(otelserver):
    assert [] == otelserver.requests

    app = TestApp(make_app(otelserver.url))

    resp = app.post('/', dict(foo='bar'))
    resp.mustcontain(b'{"status": "ok"}')

    requests = get_spans(otelserver)
    assert len(requests) != 0


def test_disabled_without_endpoint():
    config = Configurator(settings={})
    config.include('pyramid_otelapm')

    config.add_route('index', '/')
    config.add_view(
        lambda x: {'status': 'ok'}, route_name='index', renderer='json'
    )

    app = TestApp(config.make_wsgi_app())
    resp = app.get('/')
    resp.mustcontain(b'{"status": "ok"}')


def test_transactions_ignore_patterns(otelserver):
    app = TestApp(
        make_app(
            otelserver.url,
            **{'opentelemetry.transactions_ignore_patterns': 'mark_log'},
        )
    )

    resp = app.get('/mark_log')
    resp.mustcontain(b'{"status": "ok"}')

    # Give the exporter some time; no spans should ever show up for the
    # ignored route, so a short, fixed sleep is enough (and avoids waiting
    # for the full timeout of get_spans).
    time.sleep(1)
    assert [] == otelserver.requests


def test_get_transaction_name():
    class FakeRoute:
        pattern = '/foo/{id}'

    class FakeRequest:
        path = '/foo/1'
        matched_route = FakeRoute()
        method = 'GET'

    assert 'GET /foo/{id}' == pyramid_otelapm.get_transaction_name(
        FakeRequest()
    )


def test_get_transaction_name_excludes_fanstatic_resources():
    class FakeRequest:
        path = '/fanstatic/something.js'
        matched_route = None
        method = 'GET'

    assert (
        'GET resources/*subpath'
        == pyramid_otelapm.get_transaction_name(FakeRequest())
    )
