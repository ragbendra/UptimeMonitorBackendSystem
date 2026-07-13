# Uptime Monitor Backend

FastAPI backend for monitoring user-owned URLs, scheduling checks, and tracking downtime incidents.

## Run Demo

Create `.env` from `.env.example`, then start the stack:

```bash
docker compose up --build
```

Open the API docs:

```text
http://localhost:8000/docs
```

Demo flow:

1. Register with `POST /auth/register`.
2. Login with `POST /auth/login`.
3. Authorize in Swagger using `Bearer <access_token>`.
4. Create a monitor with `POST /monitors`.
5. The scheduler creates check jobs.
6. The check worker checks the URL.
7. If the URL fails twice, an incident opens and a `down` alert record is created.
8. When the URL recovers, the incident is resolved and a `recovery` alert record is created.

## Current API

### Auth

- `POST /auth/register`
  - Creates a user account.
  - Duplicate email: `Email is already registered.`

- `POST /auth/login`
  - Returns a bearer token.
  - Wrong credentials: `Email or password is incorrect.`

Use protected endpoints with:

```http
Authorization: Bearer <access_token>
```

### Monitors

All monitor endpoints require login.

- `POST /monitors`
  - Creates a monitor for the logged-in user.
  - Required fields: `name`, `target_url`, `check_interval_seconds`.
  - `target_url` must be an HTTP or HTTPS URL.
  - `check_interval_seconds` must be at least `30`.

- `GET /monitors`
  - Lists only the logged-in user's monitors.

- `GET /monitors/{monitor_id}`
  - Returns one monitor.
  - Missing or not owned: `Monitor was not found.`

- `PATCH /monitors/{monitor_id}`
  - Updates `name`, `target_url`, `check_interval_seconds`, or `status`.
  - Missing or not owned: `Monitor was not found.`

- `DELETE /monitors/{monitor_id}`
  - Deletes the monitor.
  - Missing or not owned: `Monitor was not found.`

- `GET /monitors/{monitor_id}/incidents`
  - Lists incidents and alert records for a monitor.
  - Missing or not owned: `Monitor was not found.`

## Monitor Delete Behavior

Deleting a monitor cascades deletion to its check jobs, incidents, and alert jobs.
This keeps the beginner version simple and avoids orphaned records.

## Scheduler

Run the scheduler with:

```bash
python -m workers.scheduler
```

The scheduler:

- uses a Redis lock so only one scheduler instance enqueues jobs at a time
- finds active monitors that are due for checking
- creates `check_jobs` rows for due monitors
- uses an idempotency key so the same monitor is not scheduled twice in the same time window

The scheduler only creates jobs. The check worker runs those jobs in the next module.

## Check Worker

Run the check worker with:

```bash
python -m workers.check_worker
```

The check worker:

- claims pending `check_jobs`
- checks the monitor URL
- marks the job as done
- updates `last_checked_at`
- resets `consecutive_failures` when the site is up
- increases `consecutive_failures` when the site is down

## Incidents And Alerts

The check worker now handles incidents:

- after 2 failed checks, it opens one incident
- it creates a simple `down` alert record
- when the site is up again, it resolves the incident
- it creates a simple `recovery` alert record

This version stores alert records in the database instead of sending real emails.

## Docker Services

Docker Compose runs:

- `postgres`
- `redis`
- `migrate`
- `api`
- `scheduler`
- `check_worker`
