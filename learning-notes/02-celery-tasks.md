# Celery Task Queue Module — Notes

Built in a new app: `tasks_demo`. Grounded throughout in Guardex's real
models (`vehicle.Tractor`), not hypothetical data. Reuses the same
`guardex-redis` Docker container from the caching module — Celery's broker
and result backend are just different logical Redis DBs on that same server.

---

## 1. Why Celery — the problem it solves

Every request Django handles today is **synchronous**: the client is blocked
until the view finishes all its work and returns. Fine for a fast query,
broken for anything slow (sending a notification, calling a flaky
third-party API, generating a report) — a 5s task means a 5s hung request,
and under load, worker processes tied up like that can't serve anyone else.

**Celery's job**: let a view say "do this work, but not on this
request-response cycle" — hand it off to a separate process and return the
HTTP response immediately.

## 2. Architecture: broker, worker, result backend

```
┌─────────┐  push   ┌───────────┐  pull   ┌──────────┐
│ Django  │ ──────► │  Broker   │ ◄────── │  Worker  │
│ (views) │  task    │  (Redis)  │  task   │ (Celery) │
└─────────┘          └───────────┘         └────┬─────┘
                                                 │ writes result
                                                 ▼
                                          ┌──────────────┐
                                          │Result Backend│
                                          │   (Redis)    │
                                          └──────────────┘
```

- **Broker** — where `.delay()` pushes a serialized "run this task" message.
  The view's job ends there; it never waits for execution.
- **Worker** — a *separate, long-running process* (`celery -A guardex
  worker`), completely independent of `runserver`/`gunicorn`. Watches the
  broker's queue, pulls messages off, and actually executes the task
  function. This is where the real work happens, outside the request cycle.
- **Result backend** — where the worker writes the task's outcome (return
  value or exception), keyed by task ID, since the original HTTP request is
  long gone by the time the task finishes.

**Same Redis server as the cache, different logical DBs** (Redis has 16
built-in, numbered 0–15):

| Purpose | Redis DB |
|---|---|
| Cache (`caching_demo`) | db `1` |
| Celery broker | db `2` |
| Celery result backend | db `3` |

> **Exercise asked:** if a view calls `some_task.delay(...)` and the worker
> is stopped at that moment, what happens to (1) the HTTP response, (2) the
> task itself?
> **My answer, correct on both counts:** the response is unaffected — the
> view only pushes a message onto Redis and returns, it never waits on a
> worker. The task isn't lost — it sits queued in the broker until a worker
> comes online and drains the backlog.
> **This got verified for real later** when testing the `log-tractor-status`
> endpoint with the worker down: got a clean `202` + `task_id` immediately,
> exactly as predicted.

---

## 3. Setup

Installed the package (`pip install celery`, pulled in `5.6.3`).

Added broker/result-backend settings to `guardex/guardex/settings.py`,
mirroring `CACHES`'s URL shape but on different db numbers:
```python
CELERY_BROKER_URL = 'redis://127.0.0.1:6379/2'
CELERY_RESULT_BACKEND = 'redis://127.0.0.1:6379/3'
```

Created `guardex/guardex/celery.py` — the Celery application instance,
Celery's equivalent of `wsgi.py`/`asgi.py`:
```python
import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'guardex.settings')

app = Celery('guardex')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```
- `os.environ.setdefault(...)` is needed here (unlike a normal Django module)
  because this file can be invoked standalone by the `celery` CLI, outside
  `manage.py` — it can't assume Django's settings are already loaded.
- `namespace='CELERY'` is *why* the settings above are named
  `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` — Celery strips that prefix and
  lowercases the rest to find its own config keys.
- `autodiscover_tasks()` scans every app in `INSTALLED_APPS` for a module
  literally named `tasks.py` and registers whatever it finds — no manual
  registration needed.
- `-A guardex` on the CLI (`celery -A guardex worker`) is why this file lives
  at `guardex/guardex/celery.py`, right next to `settings.py`.

Wired it into Django startup via `guardex/guardex/__init__.py` (otherwise the
app instance just sits there, unimported and unused):
```python
from .celery import app as celery_app

__all__ = ('celery_app',)
```

**Docker hiccup encountered again** (same as the Redis module): `guardex-redis`
had exited between sessions. Checked with `docker ps -a` (STATUS column shows
`Exited`), brought it back with `docker start guardex-redis` (not `docker run`
— the named container already exists), verified with `docker exec
guardex-redis redis-cli ping` → `PONG`.

Verified the whole chain: `celery -A guardex worker -l info` →
`celery@<hostname> ready.` banner, with zero tasks registered yet.

---

## 4. Writing and triggering a task

`@shared_task` turns a plain function into something Celery recognizes —
"shared" because it doesn't need to import the `celery.py` app instance
directly; it just needs to live in a file named `tasks.py`, which
`autodiscover_tasks()` specifically looks for.

`some_task(args)` runs synchronously, in whatever process calls it — no
Celery involved. `some_task.delay(args)` is the shortcut that actually
enqueues it onto the broker, returning an `AsyncResult` (a task ID) instantly
rather than the real return value.

First task, `tasks_demo/tasks.py`:
```python
@shared_task
def log_tractor_status(tractor_id):
    tractor = Tractor.objects.get(tractor_id=tractor_id)
    print(f"[log_tractor_status] {tractor.maker} {tractor.model} ({tractor.tractor_id}) - status: {tractor.status}")
    return {"tractor_id": tractor.tractor_id, "status": tractor.status}
```

> **Debugging detour:** first test run appeared to print nothing in the
> worker terminal, even though the `received` log line showed up. Turned out
> nothing was actually broken — two things were true at once: (1) plain
> `print()` inside a task gets redirected into Celery's own logger at
> **`WARNING`** level by default (`worker_redirect_stdouts_level`), so it
> shows up as a yellow `[... WARNING/ForkPoolWorker-N] ...` line, not a bare
> unformatted print — easy to miss if you're expecting exact plain-text
> output; (2) a distinctive marker string was added to the print statement
> to make it `grep`-able in noisy output — good debugging instinct, confirmed
> the print *was* there, just formatted differently than expected.

Triggering from a real endpoint (`tasks_demo/views.py`) instead of the shell:
```python
class TriggerTractorStatusLogView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        tractor_id = request.data.get('tractor_id')
        result = log_tractor_status.delay(tractor_id)
        return Response({"task_id": result.id, "message": "Task queued"}, status=status.HTTP_202_ACCEPTED)
```
`202 Accepted` (not `200`/`201`) is the right status here — signals "request
accepted, work isn't done yet," matching what's actually true. Confirmed
live: response comes back immediately regardless of whether the worker is
even running.

---

## 5. Checking a result later — the result backend, for real

Watching a live worker terminal doesn't scale. The task ID handed back from
`.delay()` is the only thread connecting an HTTP response to whatever the
worker eventually does — `celery.result.AsyncResult(task_id)` retrieves the
outcome from the result backend (Redis db `3`) at any point afterward, from
anywhere, using just that ID.

```python
class TaskStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, task_id):
        result = AsyncResult(task_id)
        return Response({
            "task_id": task_id,
            "status": result.status,          # PENDING / STARTED / SUCCESS / FAILURE
            "result": result.result if result.ready() else None,
        })
```
`result.ready()` gated the `.result` read — avoids a misleading `None` while
still running vs. a genuinely `None` return value, and sidesteps reading an
exception object mid-flight.

**Live proof**: POST `log-tractor-status/` → got back a `task_id` → GET
`task-status/<id>/` → `"status": "SUCCESS"`, `"result": {"tractor_id":
"TRC-001", "status": "active"}` — the full loop (shell/HTTP → broker →
worker → ORM query → result backend → HTTP again) confirmed working
end-to-end.

---

## 6. Add-ons covered

### Add-on 1: Periodic tasks (Celery Beat)

**Concept**: everything above only ever ran because something explicitly
called `.delay()`. Celery Beat is a **third, separate process**
(`celery -A guardex beat`) whose only job is to be a clock — on schedule, it
pushes a task message onto the broker, exactly like a view would. **Beat
never executes tasks itself** — it only enqueues them; the worker still does
the actual work. This means Beat is useless without a worker also running.

New task, grounded in real `Tractor` data:
```python
@shared_task
def log_fleet_status_summary():
    summary = {
        status: Tractor.objects.filter(status=status).count()
        for status, _label in VehicleChoices.STATUS_CHOICES
    }
    print(f"[log_fleet_status_summary] {summary}")
    return summary
```

Schedule, in `settings.py` (`timedelta` already imported for `SIMPLE_JWT`,
no new import needed):
```python
CELERY_BEAT_SCHEDULE = {
    'log-fleet-status-summary-every-30-seconds': {
        'task': 'tasks_demo.tasks.log_fleet_status_summary',
        'schedule': timedelta(seconds=30),
    },
}
```

> **Point of confusion, resolved:** after seeing `Scheduler: Sending due
> task...` in the Beat terminal, expected the `print()` output to also
> appear there. It didn't — because Beat only ever dispatches, it never runs
> task code. The actual print only ever showed up in the **worker's**
> terminal, which is running the function.

Live proof: ran `beat` + `worker` simultaneously — Beat logged
`Sending due task` every 30s, worker printed the fleet summary shortly after
each time, entirely on its own, with `runserver` not even needed (no HTTP
request involved anywhere in this flow).

### Add-on 2: Retries & error handling

**Concept**: not all task failures deserve the same response.
- **Permanent failures** (e.g. `Tractor.DoesNotExist` for a bad ID) — retrying
  changes nothing, it'll fail identically every time.
- **Transient failures** (e.g. a flaky third-party API, a momentary network
  blip) — retrying after a short delay might actually succeed.

`autoretry_for` makes this exception-type-aware, declaratively:
```python
@shared_task(autoretry_for=(ConnectionError,), retry_backoff=True, max_retries=3)
def sync_tractor_with_external_system(tractor_id):
    tractor = Tractor.objects.get(tractor_id=tractor_id)   # bad ID -> fails immediately, no retry

    if random.random() < 0.7:
        raise ConnectionError("simulated external system timeout")   # this IS retried

    print(f"[sync_tractor_with_external_system] synced {tractor.tractor_id} successfully")
    return {"tractor_id": tractor.tractor_id, "synced": True}
```
- `autoretry_for=(ConnectionError,)` — only this specific exception type
  triggers a retry. A `Tractor.DoesNotExist` still fails immediately and
  permanently, since it's not in the tuple — deliberately, since retrying a
  genuinely-bad ID would be wasted work.
- `retry_backoff=True` — delays grow between attempts (~1s, ~2s, ~4s...)
  instead of hammering immediately.
- `max_retries=3` — hard ceiling; after that, a real `FAILURE`.
- The `.get()` lookup runs *before* the simulated flaky failure, on purpose,
  so permanent vs. transient failures stay clearly separated in the code.

Since Guardex has no real flaky external service to demonstrate this against,
`random.random() < 0.7` simulates one — same trick as the artificial
`time.sleep()` used in the caching module's stampede demo: manufacture an
otherwise-invisible failure mode so it can actually be observed.

**Live proof**: `sync_tractor_with_external_system.delay("TRC-001")` from the
shell → worker terminal showed two `retry: Retry in ...` lines with growing
backoff delays, then a success print — confirming both the retry mechanism
and the backoff timing worked as designed.

### Add-on 3: Multiple queues & routing

**Concept**: by default every task flows through one queue, consumed by
whichever child process (`ForkPoolWorker-N`) in the one worker is free. A
burst of slow tasks can end up queued in front of fast ones, delaying work
that has nothing to do with the slow batch — one checkout line, one full
cart ahead of you slows down your two items regardless.

**Fix**: named queues + routing, then dedicated worker processes per queue
(`-Q` flag). Distinguished from **concurrency** (`--concurrency=N`, the
source of `ForkPoolWorker-N`) — concurrency controls how many tasks *one*
worker runs in parallel, but says nothing about *which* tasks it's allowed to
pull; routing is what actually separates that.

```python
CELERY_TASK_DEFAULT_QUEUE = 'default'   # otherwise Celery's implicit default is named 'celery'

CELERY_TASK_ROUTES = {
    'tasks_demo.tasks.log_fleet_status_summary': {'queue': 'reports'},
}
```
Everything not explicitly routed (`log_tractor_status`,
`sync_tractor_with_external_system`) falls through to `default` automatically.

Ran two independent worker processes instead of one:
```bash
celery -A guardex worker -Q default -n default_worker@%h -l info
celery -A guardex worker -Q reports -n reports_worker@%h -l info
```

**Live proof**:
1. `sync_tractor_with_external_system.delay(...)` — only ever showed up in
   `default_worker`'s terminal.
2. Beat's next tick for `log_fleet_status_summary` — only ever showed up in
   `reports_worker`'s terminal.
3. Isolation confirmed: stopped `reports_worker` entirely, re-triggered
   `sync_tractor_with_external_system` — still ran instantly via
   `default_worker`, completely unaffected.

---

## 7. Full code as it stands in `tasks_demo/` (+ project wiring)

**`guardex/guardex/celery.py`**:
```python
import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'guardex.settings')

app = Celery('guardex')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

**`guardex/guardex/__init__.py`**:
```python
from .celery import app as celery_app

__all__ = ('celery_app',)
```

**`tasks_demo/tasks.py`**:
```python
import random

from celery import shared_task

from vehicle import choices as VehicleChoices
from vehicle.models import Tractor


@shared_task
def log_tractor_status(tractor_id):
    tractor = Tractor.objects.get(tractor_id=tractor_id)
    print(f"[log_tractor_status] {tractor.maker} {tractor.model} ({tractor.tractor_id}) - status: {tractor.status}")
    return {
        "tractor_id": tractor.tractor_id,
        "status": tractor.status,
    }


@shared_task
def log_fleet_status_summary():
    summary = {
        status: Tractor.objects.filter(status=status).count()
        for status, _label in VehicleChoices.STATUS_CHOICES
    }
    print(f"[log_fleet_status_summary] {summary}")
    return summary


@shared_task(autoretry_for=(ConnectionError,), retry_backoff=True, max_retries=3)
def sync_tractor_with_external_system(tractor_id):
    tractor = Tractor.objects.get(tractor_id=tractor_id)

    if random.random() < 0.7:
        raise ConnectionError("simulated external system timeout")

    print(f"[sync_tractor_with_external_system] synced {tractor.tractor_id} successfully")
    return {"tractor_id": tractor.tractor_id, "synced": True}
```

**`tasks_demo/views.py`**:
```python
from celery.result import AsyncResult
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .tasks import log_tractor_status


class TriggerTractorStatusLogView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        tractor_id = request.data.get('tractor_id')
        result = log_tractor_status.delay(tractor_id)
        return Response({
            "task_id": result.id,
            "message": "Task queued",
        }, status=status.HTTP_202_ACCEPTED)


class TaskStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, task_id):
        result = AsyncResult(task_id)
        return Response({
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
        })
```

**`tasks_demo/urls.py`**:
```python
from django.urls import path

from .views import TriggerTractorStatusLogView, TaskStatusView

urlpatterns = [
    path('log-tractor-status/', TriggerTractorStatusLogView.as_view(), name='trigger-tractor-status-log'),
    path('task-status/<str:task_id>/', TaskStatusView.as_view(), name='task-status'),
]
```

**`guardex/guardex/settings.py`** additions:
```python
CELERY_BROKER_URL = 'redis://127.0.0.1:6379/2'
CELERY_RESULT_BACKEND = 'redis://127.0.0.1:6379/3'

CELERY_BEAT_SCHEDULE = {
    'log-fleet-status-summary-every-30-seconds': {
        'task': 'tasks_demo.tasks.log_fleet_status_summary',
        'schedule': timedelta(seconds=30),
    },
}

CELERY_TASK_DEFAULT_QUEUE = 'default'

CELERY_TASK_ROUTES = {
    'tasks_demo.tasks.log_fleet_status_summary': {'queue': 'reports'},
}
```

**Wiring outside the app:**
- `guardex/guardex/settings.py` — `'tasks_demo'` added to `INSTALLED_APPS`.
- `guardex/guardex/urls.py` — added `path('tasks-demo/', include('tasks_demo.urls'))`.

---

## 8. Mentioned but not yet covered

- **`django-celery-beat`** — the DB-backed scheduler package that lets
  schedules be edited dynamically (e.g. via Django admin) instead of being
  fixed in `settings.py`. Not needed for this module's fixed 30s demo
  interval, but the natural next step if schedules need to change at runtime.
- **Task chaining/canvas** (`chain`, `group`, `chord`) — combining multiple
  tasks into multi-step workflows (e.g. "log status, then send a
  notification"). Not touched — every task in this module stood alone.
- **Idempotency** — Celery's default delivery guarantees mean a task can in
  some failure scenarios be redelivered/run more than once; designing tasks
  to be safe under that (e.g. not double-charging, not double-sending) is a
  real concern for production tasks, not addressed here.
- Beyond `tasks_demo`'s own endpoints, none of this (tasks, retries, queues)
  has been applied to the *real* production flows yet (e.g. a real
  `Trip`-created notification) — that would be a deliberate follow-up, not
  done as part of this module.
