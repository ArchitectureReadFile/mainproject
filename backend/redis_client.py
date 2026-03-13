import os

import redis

IS_TEST = "PYTEST_CURRENT_TEST" in os.environ

if IS_TEST:
    import fakeredis

    if not hasattr(fakeredis, "_shared_server"):
        fakeredis._shared_server = fakeredis.FakeServer()

    redis_client = fakeredis.FakeStrictRedis(
        server=fakeredis._shared_server, decode_responses=True
    )
else:
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    redis_client = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True
    )
