# Uptime Monitor Backend

FastAPI backend for monitoring user-owned URLs, scheduling checks, and tracking downtime incidents.

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
