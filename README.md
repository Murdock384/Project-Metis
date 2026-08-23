# Project Metis

A scheduling app with an Expo/React Native frontend and a FastAPI backend.

## Structure

```
app/       Expo (React Native) client
backend/   FastAPI backend, managed with uv
```

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Node.js 22 (see `app/.nvmrc`).

```powershell
./setup.ps1   # runs `uv sync` for the backend and `npm install` for the app
```

Then run the backend and app in separate terminals as described below.

## Backend setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+ (uv will fetch the interpreter if needed).

```powershell
cd backend
uv sync                # creates .venv and installs dependencies from pyproject.toml/uv.lock
uv run uvicorn app.main:app --reload
```

The API serves at `http://127.0.0.1:8000`, with a health check at `/health` and docs at `/docs`.

Configuration is read from `backend/.env` (see `Settings` in [backend/app/core/config.py](backend/app/core/config.py)). By default it uses a local SQLite database (`metis.db`).

To add or remove a dependency:

```powershell
uv add <package>
uv remove <package>
```

## App setup

Requires Node.js and the Expo CLI (`npx` is enough, no global install needed).

```powershell
cd app
npm install
npm start
```

Then press `a`/`i`/`w` to launch on Android/iOS/web, or scan the QR code with Expo Go.

## Development notes

- Backend dependencies are locked via `uv.lock` — commit it alongside `pyproject.toml` changes.
- The app talks to the backend via `app/src/api` — update the base URL there if the backend isn't running on the default local address.
