from flask import Flask, render_template, request, g, session
from web.extensions import (
    rq, sentry, redis_store
)
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


def register_error_handlers(app):
    def render_error(e):
        return render_template('{}.html'.format(e.code)), e.code

    for e in [404]:
        app.errorhandler(e)(render_error)
