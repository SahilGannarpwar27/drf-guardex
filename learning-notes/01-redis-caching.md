# Redis Caching Module — Notes

Built in a new app: `caching_demo`. Grounded throughout in Guardex's real
models (`user.UserRole`, `vehicle.Tractor`), not hypothetical data.

---

## 1. Why caching, on top of ORM query optimization?

**What `select_related`/`prefetch_related` actually fix** (recap, using
`vehicle.views.TripViewSet`, which does
`Trip.objects.select_related('tractor','driver').prefetch_related('trailer')`):
they collapse N+1 queries into a small fixed number *per request*. They make
**one request cheaper** — they do nothing about **how many requests** hit
Postgres.

**The problem that's left over: repeated identical work.** Every
authenticated request in Guardex re-fetches `request.user` from Postgres via
`JWTAuthentication`, and `IsAdmin`/`IsSuperAdmin` re-check `user_role.name` —
every single call, even if nothing changed since the last one. Same story for
`UserRoleView`: it returns 4 rows that change maybe once a year, but could be
hit dozens of times a minute.

Query optimization reduces the *cost of one trip* to the database. It does
nothing about *how many trips you take* for data that hasn't changed.

**What Redis adds**: a separate in-memory tier in front of Postgres.
Cache-aside, conceptually:
```
Without cache: Client → Django → Postgres (every single time)
With cache:    Client → Django → Redis (HIT, ~0.1-1ms), Postgres untouched
               (only on a MISS does Django fall through to Postgres, then fill Redis)
```

**The trade-off caching introduces**: a cached copy can go stale the moment
the underlying row changes in Postgres — a failure mode query optimization
never has, because the ORM always reads live.

> **Exercise asked:** if `IsAdmin`/`IsSuperAdmin` are checked on every
> request, and an admin's dashboard fires 20 calls/page-load, 10 times an
> hour — how many times does Postgres get asked "what's this admin's role"
> today (no caching) vs. with a 5-minute-TTL cache?
> *(This one didn't get answered before moving on — worth revisiting: the
> uncached number is ~200/hour; with a 5-min TTL it drops to ~12/hour, since
> the role only actually gets refetched once every 5 minutes no matter how
> many requests land in that window.)*

---

## 2. Redis architecture: server vs. driver, and why `LocMemCache` isn't enough

**Redis is a separate server process, like Postgres** — not a Python
package. `django-redis` is just the driver (same role `psycopg2-binary`
plays for Postgres):

| | Server (does the work) | Python driver |
|---|---|---|
| Postgres | `postgres` on port 5432 | `psycopg2-binary` |
| Redis | `redis-server` on port 6379 | `django-redis` |

**Why Django's built-in `LocMemCache` (zero-install default) isn't enough:**
it's just a dict inside the Django process's own memory.
1. **Multi-process problem**: under `gunicorn -w 4`, each worker is an
   isolated process with its own memory — one worker caching something is
   invisible to the other 3 (same as 4 browser tabs with separate
   `localStorage`s that don't sync). Redis is one external server all
   workers share.
2. **Restart problem**: `LocMemCache`'s data lives and dies with the Django
   process — restart/redeploy/crash wipes it. Redis is a separate long-lived
   process, so it survives Django restarts (and can persist to disk itself).

> **Exercise asked:** would the multi-process problem bite us *today* (single
> `runserver` process)? What's a *different* reason `LocMemCache` is bad even
> in single-process dev?
> **My answer, corrected once:** I first said "yes it'd bite today" — wrong,
> since `runserver` is a single process, there's no second worker to be
> unaware of the cache. It's a *future* problem (once deployed under
> gunicorn). The single-process reason: restarting the server wipes the
> cache, since it's tied to the Django process's own memory. **I got this
> one right on the second half unprompted.**

**Redis "databases"**: one Redis server has 16 numbered logical databases
(0–15) built in — cheap built-in namespacing (e.g. cache data in db `1`,
future Celery broker data in a different db number), unrelated to Postgres's
per-project databases.

---

## 3. Setup: getting Redis actually running

Chose to run Redis via **Docker** (over a native `apt install redis-server`)
for isolation and easy reset:
```bash
docker run -d --name guardex-redis -p 6379:6379 redis:latest
docker exec guardex-redis redis-cli ping   # → PONG confirms the server is alive
```

Installed the Python driver into the venv:
```bash
pip install django-redis   # pulls in `redis` (the actual protocol client) as a dependency
```

Wired it into `guardex/guardex/settings.py`:
```python
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',   # db index 1
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
```

> **Exercise asked:** given `DATABASES` uses `ENGINE` + `HOST`/`PORT`, what
> would `CACHES` need, structurally?
> **My answer:** guessed `ENGINE: django-redis`, `PORT: 6379`.
> **Correction:** the key is `BACKEND` (not `ENGINE`), and its value is a full
> Python class path (`django_redis.cache.RedisCache`), not just a package
> name. Host+port aren't separate keys — they're combined into one
> `LOCATION` URL string.

> **Exercise asked:** if `django-redis` is installed but no `redis-server` is
> actually running, what happens on `cache.set(...)`?
> **My answer:** "no idea."
> **Answer given:** it raises `redis.exceptions.ConnectionError` /
> `django_redis.exceptions.ConnectionInterrupted` ("Connection refused") —
> same failure shape as `psycopg2` when Postgres is down. No silent no-op,
> no automatic fallback to memory.
>
> **This actually happened for real later in the session** — the
> `guardex-redis` container had stopped (environment reset between turns),
> and running the verification command below hit exactly this
> `ConnectionError`. Fixed with `docker start guardex-redis` (not
> `docker run` again, since the named container already existed).

Verified the whole chain end-to-end via `manage.py shell`:
```python
from django.core.cache import cache
cache.set('hello', 'world', timeout=30)
cache.get('hello')   # → 'world'
```

---

## 4. The cache-aside pattern

> **Exercise asked:** describe, in plain English, what `UserRoleView.get()`
> should do to avoid hitting Postgres every time.
> **My answer:** "hit Postgres first time and store in Redis; next time
> check Redis first."
> **Refinement given:** it's not that the *first* call is special-cased in
> code — it's the *same code path* every time; only the outcome differs
> based on whether the key already exists:
> ```
> 1. Request comes in → check Redis for the key
> 2. MISS  → query Postgres → store result in Redis with a TTL → return it
> 3. (later) Request comes in → check Redis again
> 4. HIT   → return directly, Postgres untouched
> 5. (after TTL expires) Redis auto-deletes the key → back to step 2
> ```

Built `CachedUserRolesView` (see code section below) implementing exactly
this against the real `UserRole` table. Verified live:
- Call 1 (miss): `postgres (cache miss)`, **13.25ms**
- Call 2 (hit): `redis (cache hit)`, **0.536ms** — ~25x faster
- Inspected the real key in Redis directly:
  `redis-cli -n 1 KEYS '*'` → `:1:demo_user_roles`
  (the `:1:` is `django-redis`'s own key-versioning prefix, default version
  `1` — useful later for mass-invalidating everything by just bumping the
  version number)
  `redis-cli -n 1 TTL ":1:demo_user_roles"` → `3550` (counting down from the
  3600s/1hr timeout we set — confirms it's a real, expiring key)

---

## 5. Cache invalidation — the hard part

Copying the exact same cache-aside pattern onto `Tractor`'s list (where
`status` changes constantly, unlike `UserRole`) breaks down:

> **Exercise asked:** admin does `PATCH` setting a tractor's `status` to
> `under_maintenance` at 2:00pm; the cached list was stored at 1:30pm with
> `status='idle'`, TTL expires at 2:30pm. What does a dispatcher loading the
> dashboard between 2:00–2:30pm see, and why?
> **My answer:** correctly identified that since `Tractor.status` "gets
> changed whenever the admin changes it" (unlike `UserRole`), "we should be
> aware to cancel the redis cache if the status of the tractor gets
> changed."
> **Elaboration given:** the write path (Postgres) and read path (Redis
> cache) are now two systems that can disagree — nothing keeps them in sync
> except time (the TTL). Two strategies: **passive** (do nothing, just
> accept staleness ≤ TTL — fine for `UserRole`) vs. **active invalidation**
> (explicitly clear the cache the moment the underlying row changes).

> **Exercise asked:** for `Tractor.status`, which strategy, and *where*
> should the invalidation logic live, given a `Tractor` can be changed via
> `TractorViewSet`, `create_demo_tractors`, Django admin, or a future Celery
> task — not just one code path?
> **My answer:** "signal or middleware."
> **Correction given:** middleware only sees the request/response cycle — it
> has no visibility into admin-panel edits, management commands, or Celery
> writes, so it would silently miss most of those paths. A Django **signal**
> (`post_save`/`post_delete`) is attached to the *model itself* and fires on
> every `.save()`/`.delete()` regardless of what triggered it — the right
> tool here.

Implemented `caching_demo/signals.py` (below), wired via `apps.py.ready()`.
Verified live end-to-end:
1. `Tractor.objects.first()` → `status='active'`
2. `t.status = 'under_maintenance'; t.save()`
3. `redis-cli EXISTS ":1:demo_tractor_list"` → `0` (signal already deleted it)
4. Next `GET` → `postgres (cache miss)`, returns the fresh
   `under_maintenance` status — no TTL wait needed.

---

## 6. Add-ons covered

### Add-on 1: Cache stampede / thundering herd

**Problem**: our plain cache-aside code has *no coordination* between
concurrent requests. If the TTL expires while many requests land in the same
instant (e.g. 200 dispatcher dashboards polling right as a 5-min TTL lapses),
**all of them** independently see a miss and **all of them** hit Postgres at
once — the exact spike caching was meant to prevent, just concentrated into
one burst.

**Analogy used** (frontend, since I'm coming from that background): React
Query deduplicating simultaneous `useQuery` calls for the same key — first
caller fires the real fetch, others subscribe to that same in-flight result
instead of each firing their own request. Same idea backend-side, except
there's no shared JS memory across processes/workers, so the "is someone
already fetching this?" flag has to live somewhere external and shared —
Redis.

**Mechanism**: `cache.add(key, value, timeout)` is atomic "set only if it
doesn't already exist" (Redis `SETNX`) — returns `True` for exactly one
caller (the "winner"), `False` for everyone else (the "losers").

> **Exercise asked (multiple choice):** what should a "loser" do — (A) error
> out immediately, (B) wait briefly then re-check the cache, (C) query
> Postgres anyway?
> **My answer:** B — correctly reasoned A breaks the response entirely, and C
> defeats the whole purpose of adding Redis.

> **Follow-up asked:** what happens to all the waiting "losers" if the
> "winner" process crashes *after* acquiring the lock but *before* finishing
> the query and releasing it?
> **My answer:** "all the losers will wait and eventually will not get the
> data" — correctly identified the deadlock risk.
> **Fix given:** the lock key itself needs its own short TTL (separate from
> the data's TTL) as a safety valve — if the winner dies mid-work, Redis
> auto-expires the lock and the next request becomes a fresh winner.
> Self-healing instead of permanently stuck.

**Live proof** (`CachedTractorListView`, with an artificial 1s delay added to
make the race observable): 6 concurrent requests on a cold cache →
1 `postgres (winner - cache miss)` (~1047ms) + 5
`redis (loser - waited for winner)` (~1113-1140ms) — only *one* real Postgres
query despite 6 simultaneous requests. Re-running the same 6 concurrent
requests against the now-warm cache → all 6 `redis (cache hit)` (~1-4ms each),
no locking path even engaged.

> **Exercise asked:** rerunning the same test immediately after — same
> "1 winner, 5 losers" pattern, or different?
> **My answer:** correctly predicted all 6 would get the data directly from
> Redis this time, since it's already stored — confirmed live.

### Add-on 2: A reusable caching abstraction (DRY)

**Problem**: the cache-aside + lock logic was ~25 lines duplicated per view.

**Decision**: built a **mixin** (`CacheAsideMixin`), not a decorator —
because Guardex is 100% class-based views (`APIView`/`ModelViewSet`, zero
function-based views), and DRF's own architecture is already built from
mixins (`ListModelMixin`, etc.). A decorator would've had no actual use case
in this codebase, so it was deliberately skipped rather than built unused.

Refactored both `CachedUserRolesView` and `CachedTractorListView` to inherit
`CacheAsideMixin` — each now only declares `cache_key`, `cache_ttl`, and
`get_fresh_data()`; the entire check/lock/wait/fallback sequence lives in one
place. Re-tested both endpoints afterward to confirm identical behavior
(miss/hit for roles; 1-winner/3-loser stampede protection for tractors) —
no regressions from the refactor.

### Add-on 3: `bulk_update`/`bulk_create` silently bypass signals

**Concept**: Django signals fire *from inside* `Model.save()`/`delete()`.
Bulk ORM methods (`queryset.update(...)`, `bulk_create`, `bulk_update`)
compile directly to one raw SQL statement and **never call `.save()` at
all** — so `post_save` never fires. This is documented Django behavior, not
a bug, traded for write performance.

**Concrete risk**: a "maintenance day" script doing
`Tractor.objects.filter(id__in=[...]).update(status='under_maintenance')`
is the idiomatic Django way to write that — and it would silently leave the
cached tractor list stale for up to the full TTL, no errors anywhere.

> **Exercise asked:** predict the outcome of
> `Tractor.objects.filter(tractor_id='TRC-001').update(status='active')`
> right after a `GET` — what would the cached endpoint show?
> **My answer:** "active" — the intuitive-but-wrong answer, reasoning "that's
> what we just told the database to set."
> **Correction given:** because `.update()` bypasses `.save()`, the
> `post_save` signal never fires, so the cache key from the *previous* state
> is never invalidated — the endpoint would keep serving the old cached
> value until the TTL naturally expires, even though Postgres is already
> correct.

**Live demo** (first attempt actually failed to prove the point — the cache
had gone cold from unrelated Docker container restarts during the session,
so the "miss" that resulted looked correct by accident; redone properly by
explicitly warming the cache first):
1. `t.status = 'under_maintenance'; t.save()` → Postgres: `under_maintenance`
2. `GET` → warms cache with `under_maintenance`
3. `redis-cli EXISTS` → `1` (cached)
4. `Tractor.objects.filter(...).update(status='active')` → Postgres: `active`
5. `redis-cli EXISTS` → still `1`, **untouched** by any signal
6. `GET` → `redis (cache hit)`, returns **`under_maintenance`** — stale,
   despite Postgres genuinely saying `active`. Bug confirmed live.

**Mitigations discussed** (not implemented as a permanent fix yet — flagged
as a possible follow-up):
1. Avoid bulk ORM methods on cached models when correctness matters more
   than write speed; loop + `.save()` per instance instead (slower, but
   signal-safe).
2. Explicitly invalidate the cache manually right after any bulk write —
   puts the burden back on the developer, exactly the fragility signals were
   meant to avoid, but sometimes unavoidable.
3. Keep TTLs short enough that staleness has a hard ceiling regardless of
   whether invalidation fires — defense-in-depth, not a fix.

---

## 7. Full code as it stands in `caching_demo/`

**`caching_demo/mixins.py`** — the reusable cache-aside + stampede-lock core:
```python
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
    lock_ttl = 10                    # safety valve: auto-releases even if the winner crashes
    lock_wait_retry_interval = 0.1   # how often "losers" re-check whether the winner is done
    lock_wait_max_retries = 30       # ~3s max wait before giving up and querying directly

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

        # atomic "set only if not already set" -> True for exactly one caller
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
```

**`caching_demo/views.py`** — two demo endpoints built on the mixin, one for
near-static data (`UserRole`), one for frequently-changing data (`Tractor`):
```python
import time

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from user.models import UserRole
from user.serializers import UserRoleSerializer
from vehicle.models import Tractor
from vehicle.serializers import TractorSerializer

from .mixins import CacheAsideMixin

CACHE_KEY = "demo_user_roles"
CACHE_TTL_SECONDS = 60 * 60  # UserRole barely ever changes, so a long TTL is safe

TRACTOR_CACHE_KEY = "demo_tractor_list"
TRACTOR_CACHE_TTL_SECONDS = 60 * 60  # long TTL is safe here BECAUSE the signal in
                                     # signals.py invalidates it immediately on any write

SIMULATED_QUERY_DELAY_SECONDS = 1  # artificial slowdown so concurrent requests can race


class CachedUserRolesView(CacheAsideMixin, APIView):
    """Cache-aside demo using the real UserRole table."""
    permission_classes = [AllowAny]
    cache_key = CACHE_KEY
    cache_ttl = CACHE_TTL_SECONDS

    def get_fresh_data(self):
        roles = UserRole.objects.all()
        return UserRoleSerializer(roles, many=True).data

    def get(self, request):
        start = time.perf_counter()
        data, source = self.get_cached_data()
        elapsed_ms = round((time.perf_counter() - start) * 1000, 3)
        return Response({
            "source": source,
            "elapsed_ms": elapsed_ms,
            "roles": data,
        })


class CachedTractorListView(CacheAsideMixin, APIView):
    """
    Cache-aside + stampede protection for Tractor's list, for data that
    actually changes (Tractor.status) - safe here only because the
    signal in signals.py invalidates the cache on every write.
    """
    permission_classes = [AllowAny]
    cache_key = TRACTOR_CACHE_KEY
    cache_ttl = TRACTOR_CACHE_TTL_SECONDS

    def get_fresh_data(self):
        tractors = Tractor.objects.all()
        time.sleep(SIMULATED_QUERY_DELAY_SECONDS)  # pretend this is an expensive query
        return TractorSerializer(tractors, many=True).data

    def get(self, request):
        start = time.perf_counter()
        data, source = self.get_cached_data()
        elapsed_ms = round((time.perf_counter() - start) * 1000, 3)
        return Response({
            "source": source,
            "elapsed_ms": elapsed_ms,
            "tractors": data,
        })
```

**`caching_demo/signals.py`** — invalidates the tractor cache on *any* write
path, not just the API:
```python
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from vehicle.models import Tractor

from .views import TRACTOR_CACHE_KEY


@receiver(post_save, sender=Tractor)
@receiver(post_delete, sender=Tractor)
def invalidate_tractor_cache(sender, instance, **kwargs):
    cache.delete(TRACTOR_CACHE_KEY)
```

**`caching_demo/apps.py`** — signals do nothing until actually imported;
`ready()` is Django's guaranteed-once-at-startup hook for that:
```python
from django.apps import AppConfig


class CachingDemoConfig(AppConfig):
    name = 'caching_demo'

    def ready(self):
        from . import signals  # noqa: F401 - import registers the @receiver hooks
```

**`caching_demo/urls.py`**:
```python
from django.urls import path

from .views import CachedUserRolesView, CachedTractorListView

urlpatterns = [
    path('roles/', CachedUserRolesView.as_view(), name='cached-roles'),
    path('tractors/', CachedTractorListView.as_view(), name='cached-tractors'),
]
```

**Wiring outside the app:**
- `guardex/guardex/settings.py` — added `'caching_demo'` to
  `INSTALLED_APPS`, and the `CACHES` block shown in section 3.
- `guardex/guardex/urls.py` — added
  `path('caching-demo/', include('caching_demo.urls'))`.

---

## 8. Mentioned but not yet covered

- **Fixing the bulk-update gotcha for real** — we demonstrated the bug
  (section 6, add-on 3) but didn't implement any of the three mitigations
  as actual code in `caching_demo`.
- **Celery** — flagged as the next module after this one; not started.
- Beyond the two apps' worth of demo endpoints, we never applied any of this
  (mixin, signals, locking) to the *real* production endpoints
  (`TractorViewSet`, `TrailerViewSet`, `TripViewSet`, `UserRoleView`) — only
  to the parallel demo views in `caching_demo`. If/when this pattern goes into
  production code, that's a deliberate follow-up step, not done yet.
