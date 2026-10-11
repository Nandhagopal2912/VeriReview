from cache.core import Cache
from tests.support import FakeLoader, check_cache


def test_update():
    cache = Cache(FakeLoader())
    cache.get("a")
    cache.update("a", 2)
    check_cache(cache, "a")
