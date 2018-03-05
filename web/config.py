import os


class base_config(object):
    SERVER_NAME = os.environ.get('SERVER_NAME')
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SENTRY_DSN = os.environ.get('SENTRY_DSN')
    REDIS_HOST = os.environ.get('REDIS_HOST')
    REDIS_PORT = int( os.environ.get('REDIS_PORT', 6379) )
    REDIS_URL = "redis://{}:{}/0".format(REDIS_HOST, REDIS_PORT)
    RQ_REDIS_URL = REDIS_URL


class dev_config(base_config):
    DEBUG = True
