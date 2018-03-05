from flask import Flask, render_template, request, g, session, Response
from web.extensions import (
    rq, sentry, redis_store
)
import rq_dashboard
from web import config


def create_app(config=config.base_config):
    app = Flask(__name__)
    app.config.from_object(config)

    register_extensions(app)
    register_error_handlers(app)
    register_blueprints(app)
    return app


def register_extensions(app):
    rq.init_app(app)
    sentry.init_app(app, dsn=app.config['SENTRY_DSN'])
    redis_store.init_app(app)


def register_blueprints(app):
    from .views import front
    app.register_blueprint(front)

    def add_basic_auth(blueprint, username, password, realm='RQ Dashboard'):
        """Add HTTP Basic Auth to a blueprint.
        Note this is only for casual use!
        """

        @blueprint.before_request
        def basic_http_auth(*args, **kwargs):
            auth = request.authorization
            if (auth is None or auth.password != password or
                    auth.username != username):
                return Response(
                    'Please login',
                    401,
                    {'WWW-Authenticate': 'Basic realm="{0}"'.format(realm)})

    add_basic_auth(rq_dashboard.blueprint, app.config.get('RQ_DASHBOARD_USERNAME', 'hi'), app.config.get('RQ_DASHBOARD_PASSWORD', 'bye'))
    app.register_blueprint(rq_dashboard.blueprint, url_prefix="/rq")


def register_error_handlers(app):
    def render_error(e):
        return render_template('{}.html'.format(e.code)), e.code

    for e in [404]:
        app.errorhandler(e)(render_error)
