# cowhorse

## API Runtime (FastAPI)

This project now runs the `cowhorse_v2` API on FastAPI for Azure Web App.

### Local run

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Health endpoint: `GET /health`

### Azure Web App startup command

```bash
gunicorn --bind=0.0.0.0 --timeout 600 --workers 4 --worker-class uvicorn.workers.UvicornWorker app:app
```
