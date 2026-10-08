## Teaching Mode

I am learning backend dev (DRF, ORM, Redis, Celery, deployment) on top of an
existing DRF + PostgreSQL project. Consider me as a beginner as i am mostly from frontend background.

Rules for every topic:

- Explain the concept and WHY it's needed before writing any code.
- Use this project's own real models for every example — if there is a need to create new model for the explanation of the topic ask and make me to create it .
- Prefer concrete, visual walkthroughs (SQL-level, request/response flow,
  timeline diagrams) over abstract descriptions.
- You can Extend the existing app so use the context and code or can Create a new Django app per topic (e.g. `caching_demo`, `tasks_demo`).
- Go step by step: one sub-concept at a time. Give me a small exercise
  after each sub-concept and WAIT for my answer before moving further.
- At the end of the core topic, list 2-3 "add-on" advanced concepts I can
  optionally go deeper on.

"Exception — the
Deployment module is infrastructure spanning the whole project, not a
per-topic Django app. Use a deploy/ folder and root-level config files
(Dockerfile, docker-compose.yml, .github/workflows/) instead."

## Practice Mode (hands-on learning)

For every new sub-concept:

1. Explain the concept first.
2. Give me a specific task spec: which file, what function/endpoint,
   expected behavior, and hints if needed — but NOT the code itself.
3. I will write the code myself in my editor and run any
   application-level commands (runserver, shell, migrations, celery
   worker, etc.) myself in my own terminal.
4. Do NOT write implementation code or run those commands for me during
   this step.
5. Routine scaffolding (e.g. `startapp`, empty file/folder creation) is
   fine for you to do — that's not the part I'm trying to learn.
6. When I say "done" or paste my code/diff, review it: point out bugs,
   better patterns, what I got right. Then we decide whether to move on.
7. Only write the full solution yourself if I explicitly say "show me
   the answer" or "I'm stuck, just show me."

## Project Overview

Real project name: **Guardex** — fleet/trucking management backend (the
bookstore schema above is only a _teaching example_, not the real schema).
Django project root: `guardex/` (contains `manage.py`).

**Stack**: Django 6.0.4, DRF, PostgreSQL, `rest_framework_simplejwt` (JWT,
with token blacklist app), `django-filter`, `django-phonenumber-field`,
`django-redis` + Redis (caching, `caching_demo`), `celery` + Redis
(task queue, `tasks_demo` — broker db `2`, result backend db `3`, cache
db `1` on the same `guardex-redis` Redis server). No CORS yet.

**Apps**:

- `user/` — auth & RBAC.
  - Models: `User` (custom, `AbstractBaseUser`+`PermissionsMixin`,
    `USERNAME_FIELD='phone_number'`, license/medcard fields, FK →
    `UserRole`, FK → `Organization`), `UserRole` (choices: super_admin,
    admin, field_assistant, driver — see `user/choices.py`), `Organization`
    (multi-tenancy).
  - `LoginView`/`logoutView` (plain `APIView`, custom `authenticate()` in
    `guardex/utils/authenticate.py`), `UserViewSet` (`ModelViewSet`, soft
    delete via `is_active=False`, `/me` action), `OrganizationUserViewSet`,
    `UserRoleView`.
- `vehicle/` — fleet management.
  - Models: `Tractor`, `Trailer`, `Trip` (FK → `Tractor`, FK →
    `user.User` as driver, M2M → `Trailer` through explicit
    `TripTrailerRel`). All use ID prefixes (`TRC`/`TRL`/`TRK`) auto-applied
    in serializer `validate_*` methods.
  - `TractorViewSet`/`TrailerViewSet`/`TripViewSet`, all `ModelViewSet` +
    `DefaultRouter`, permission `IsAdmin` (custom, in
    `guardex/utils/permission.py`).

**Shared code** lives in `guardex/guardex/` (the project config package, not
an app): `models/TimeStamp.py` (abstract `created_at`/`updated_at` base used
by nearly every model), `utils/permission.py` (`IsAdmin`, `IsSuperAdmin`),
`utils/filters.py` (`TractorFilter`), `utils/pagination.py`
(`CustomPagination`, page_size=5), `utils/authenticate.py`.

**Patterns**: All CRUD is `ModelViewSet` + `DefaultRouter` (no generic
views). Auth-adjacent endpoints are plain `APIView`. Root urlconf mounts
`user/`, `vehicle/`, `admin/`, `token/refresh/`.

**Known rough edges** (useful to know before extending):

- No `requirements.txt`/`pyproject.toml` — deps only exist in the local
  venv (`Django`, `djangorestframework`, `djangorestframework_simplejwt`,
  `django-filter`, `django-phonenumber-field`, `psycopg2-binary`).
- `settings.py` has hardcoded `SECRET_KEY` and DB credentials, no env vars.
- `IsAdmin` permission checks for the exact role `admin` — `super_admin`
  users are blocked from `vehicle` endpoints (role hierarchy gap).
- Only `Tractor` has filtering/pagination wired up; `Trailer`/`Trip` don't.
- `vehicle/admin.py` registers no models.
- No tests beyond stub files (`user/tests.py`, `vehicle/tests.py`).

## Deployment Module

Phased order: concept → local Gunicorn → local Nginx → Docker (Django +
Postgres + Redis + Celery worker/beat) → VPS → CI/CD (GitHub Actions) →
HTTPS/logging/zero-downtime deploys.

Done: concept (WSGI, reverse proxy), local Gunicorn (multi-worker,
crash/respawn), local Nginx (reverse proxy to Gunicorn on 127.0.0.1:8001,
`/static/` served directly via `STATIC_ROOT` + `collectstatic`, hit and
fixed a `www-data` home-dir traversal 403), Docker (`Dockerfile` +
root-level `docker-compose.yml` with `web`/`db`/`redis`/`celery_worker`/
`celery_beat` services; `settings.py` DB/Redis values externalized to
env vars with local defaults preserved; hit and fixed a `celery_worker`
queue-routing bug — needed `-Q default,reports` to match
`CELERY_TASK_ROUTES` — and a missing-migrations issue on the fresh
containerized Postgres volume; full stack verified end-to-end).

Currently on: **Phase 5 — VPS** (moving the Docker Compose stack to a
real VPS). Per the Teaching Mode exception, this uses root-level
`Dockerfile`/`docker-compose.yml`/`deploy/` files, not a new Django app.

## Progress

- Redis caching (caching_demo) — completed, see learning-notes/01-redis-caching.md
- Celery task queue (tasks_demo) — completed, see learning-notes/02-celery-tasks.md
- Deployment — in progress, see Deployment Module section above for phase
