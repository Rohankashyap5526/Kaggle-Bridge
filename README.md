# Kaggle Bridge

Secure Kaggle MCP server for dataset discovery/downloads, competition discovery/data downloads, Jupyter notebook creation/execution, submission inspection, and explicitly approved competition submissions.

## Security
- Kaggle credentials are provided only through environment variables or a local `~/.kaggle/kaggle.json`.
- Never commit credentials, `.env` files, notebooks containing secrets, or Kaggle datasets.
- Cloud HTTP mode requires `MCP_AUTH_TOKEN` (minimum 32 characters) and protects every MCP HTTP route with bearer authentication. `/healthz` is intentionally unauthenticated for host health checks.
- Render environment settings must hold `KAGGLE_USERNAME`, `KAGGLE_KEY`, and `MCP_AUTH_TOKEN` as secrets.
- Notebook execution runs arbitrary Python with the server user's permissions. Execute only trusted notebooks.
- Competition submissions require explicit approval for the exact competition and file.

## Local Windows setup
```powershell
cd server
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python server.py
```
Place Kaggle's API token at `%USERPROFILE%\.kaggle\kaggle.json`, or set `KAGGLE_USERNAME` and `KAGGLE_KEY` in the environment.

## Render deployment
1. In Render, choose **New → Blueprint** and select this repository.
2. Render reads `render.yaml`, builds the Docker image, creates a persistent data disk, and generates `MCP_AUTH_TOKEN`.
3. Add `KAGGLE_USERNAME` and `KAGGLE_KEY` in the Render service's secret environment settings.
4. Deploy. Health check: `/healthz`; MCP transport: Streamable HTTP.
5. Use the bearer token when connecting an MCP client. Never publish the endpoint without authentication.

The included blueprint uses a paid Render Starter instance and a 10 GB persistent disk. A persistent disk is required to retain downloaded datasets and notebooks across restarts.

## CI
GitHub Actions runs on pushes, pull requests, and manual dispatch. It installs dependencies, compiles Python, verifies registered MCP tools, runs the auth middleware tests, and builds the Docker image. It requires no Kaggle credentials.

## MCP tools
- `kaggle_status`
- `search_datasets`, `download_dataset`
- `search_competitions`, `download_competition_data`
- `create_notebook`, `run_notebook`
- `inspect_submission`, `submit_competition_entry`

Kaggle competition rules must be accepted on Kaggle before downloading restricted competition files. The package contains no credentials.
