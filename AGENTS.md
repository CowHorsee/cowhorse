# AGENTS.md

Repository guide for autonomous coding agents working in `cowhorse`.

## 1) Project Overview

- Backend framework: FastAPI (ASGI).
- Entrypoint module: `app.py` (exports `app` from `main.py`).
- API routing root: `api/v1/router.py` with prefix `/api`.
- Health endpoint: `GET /health`.
- Data store: Azure Table Storage via `db/table_storage.py` (`DBHelper`).
- Business logic: `services/`.
- HTTP layer only: `api/v1/endpoints/`.
- Data validation models: `schemas/`.
- Shared app concerns: `core/`.
- External integrations: `integrations/` (email/pdf).

## 2) Rules Sources (Cursor/Copilot)

- `.cursor/rules/`: not present.
- `.cursorrules`: not present.
- `.github/copilot-instructions.md`: not present.
- No additional agent policy files were found in this repository.

## 3) Environment & Dependencies

- Python: 3.12+ recommended (workflow uses 3.12).
- Install runtime deps:

```bash
python -m pip install -r requirements.txt
```

- Install dev deps:

```bash
python -m pip install -r requirements-dev.txt
```

- Key env vars for full functionality:
  - `AZURE_STORAGE_CONNECTION_STRING`
  - `SMTP_SERVER`
  - `SMTP_PORT`
  - `SMTP_USERNAME`
  - `SMTP_PASSWORD`
  - `EMAIL_SENDER_ADDRESS`

## 4) Run Commands

- Local dev server (recommended):

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

- Production-like local run:

```bash
bash startup.sh
```

- Direct gunicorn ASGI command (equivalent):

```bash
gunicorn --bind=0.0.0.0 --timeout 600 --workers 2 --worker-class uvicorn.workers.UvicornWorker app:app
```

- Important: do **not** use plain `gunicorn app:app` (WSGI sync worker is incompatible with FastAPI).

## 5) Build / Lint / Test Commands

### Syntax / compile sanity

```bash
python -m compileall app.py main.py api core db services schemas integrations
```

### Type checking

```bash
python -m basedpyright --level error app.py main.py api core db services schemas integrations
```

### Run all tests

```bash
python -m pytest
```

### Run a single file

```bash
python -m pytest tests/test_health.py -q
```

### Run a single test function (most important)

```bash
python -m pytest tests/test_health.py::test_health -q
```

### Filter tests by keyword

```bash
python -m pytest -k health -q
```

## 6) Code Organization Conventions

- Keep endpoint modules thin:
  - parse/validate request
  - call service function
  - convert known failures to `HTTPException`
- Keep business rules in `services/`, not in endpoints.
- Keep Table Storage details in `db/table_storage.py`.
- Keep cross-cutting app configuration in `core/`.
- Keep external side effects in `integrations/`.

## 7) Style Guidelines

### Imports

- Use absolute imports from root packages (`api`, `services`, `core`, etc.).
- Group imports in this order: stdlib, third-party, local.
- Avoid wildcard imports.

### Formatting

- Follow PEP 8.
- Use 4-space indentation.
- Keep line length readable (prefer <= 100-120).
- Keep functions focused and short where practical.

### Types

- Add type hints for function args and return types in new/changed code.
- Use explicit container types (`dict[str, int]`, `list[str]`) where known.
- Avoid `Any` unless unavoidable for SDK/pandas boundaries.

### Naming

- Modules/files: `snake_case.py`.
- Functions/variables: `snake_case`.
- Classes: `PascalCase`.
- Constants: `UPPER_SNAKE_CASE`.

### Error Handling

- Raise `HTTPException` in endpoint layer for HTTP responses.
- Keep exceptions contextual (`raise ... from exc`).
- Do not use empty `except` blocks.
- Do not swallow errors silently; log or return explicit errors.

### Logging

- Use `logging` for integration/runtime failures.
- Keep logs actionable (include operation + identifier).
- Never log credentials/secrets.

## 8) FastAPI-Specific Conventions

- Route prefixes remain stable under `/api`.
- Use Pydantic schemas in `schemas/` for request bodies.
- Keep response shapes backward-compatible unless requested.
- Health endpoint should remain lightweight and unauthenticated.
- When updating the FastAPI `version` in `main.py`, also update the Swagger `description` last-updated timestamp in the same change.

## 9) Data Layer Conventions (Azure Table Storage)

- Use `DBHelper` methods (`extract`, `load`, `modify`, `delete`, `upsert`).
- Preserve `PartitionKey`/`RowKey` behavior via helper utilities.
- Sanitize keys using `sanitize_key` before storage lookups/updates.
- Be careful with numeric coercion and null handling in pandas->entity conversion.

## 10) Deployment Notes

- Azure Web App should run ASGI worker class.
- Preferred startup command in Azure App Service:

```bash
bash startup.sh
```

- If set manually in portal, use the direct ASGI gunicorn command above.

## 11) Agent Working Agreement

- Before edits: inspect existing patterns in nearby files.
- After edits: run compile, typecheck, and relevant tests.
- For API changes: smoke-test `GET /health` at minimum.
- Keep changes focused; do not refactor unrelated areas unless necessary.
- Do not commit unless explicitly requested.