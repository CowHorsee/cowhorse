# cowhorse

## API Runtime (FastAPI)

This project now runs the `cowhorse_v2` API on FastAPI for Azure Web App.

### Local run

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Health endpoint: `GET /health`

### Azure Web App startup command

```bash
bash startup.sh
```

Equivalent direct command:

```bash
gunicorn --bind=0.0.0.0 --timeout 600 --workers 2 --worker-class uvicorn.workers.UvicornWorker app:app
```

Do not use plain `gunicorn app:app` for FastAPI. That starts WSGI sync workers and will fail with:
`TypeError: FastAPI.__call__() missing 1 required positional argument: 'send'`.
