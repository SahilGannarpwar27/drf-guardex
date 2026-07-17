import time

from django.core.cache import cache


class CacheAsideMixin:
    """
    Generic cache-aside + stampede-lock logic for DRF views.

    Subclasses must set `cache_key` and implement `get_fresh_data()`.
    Everything else (locking, waiting, fallback) is handled here so it
    only needs to be written - and fixed - once.
    """
    cache_key = None
    cache_ttl = 60 * 60
    lock_ttl = 10
    lock_wait_retry_interval = 0.1
    lock_wait_max_retries = 30

    def get_cache_key(self):
        assert self.cache_key, f"{self.__class__.__name__} must set cache_key"
        return self.cache_key

    def get_lock_key(self):
        return f"{self.get_cache_key()}:lock"

    def get_fresh_data(self):
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement get_fresh_data()"
        )

    def get_cached_data(self):
        """Returns (data, source_label) using cache-aside + stampede lock."""
        cache_key = self.get_cache_key()

        data = cache.get(cache_key)
        if data is not None:
            return data, "redis (cache hit)"

        acquired = cache.add(self.get_lock_key(), "1", timeout=self.lock_ttl)

        if acquired:
            try:
                data = self.get_fresh_data()
                cache.set(cache_key, data, timeout=self.cache_ttl)
            finally:
                cache.delete(self.get_lock_key())
            return data, "postgres (winner - cache miss)"

        # loser: someone else is already fetching - wait for them
        for _ in range(self.lock_wait_max_retries):
            time.sleep(self.lock_wait_retry_interval)
            data = cache.get(cache_key)
            if data is not None:
                return data, "redis (loser - waited for winner)"

        # winner never finished in time - fall back rather than hang forever
        return self.get_fresh_data(), "postgres (loser - gave up waiting, fallback)"
