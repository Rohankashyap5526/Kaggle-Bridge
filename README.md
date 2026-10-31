# Kaggle Bridge

Secure Kaggle MCP server for dataset discovery/downloads, competition discovery/data downloads, Jupyter notebook creation/execution, submission inspection, and explicitly approved competition submissions.

## Security
- Kaggle credentials are provided only through environment variables or a local `~/.kaggle/kaggle.json`.
- Never commit credentials, `.env` files, notebooks containing secrets, or Kaggle datasets.
- Cloud HTTP mode requires `MCP_AUTH_TOKEN` (minimum 32 characters) and protects every MCP HTTP route with bearer authentication. `/healthz` is intentionally unauthenticated for host health checks.
- Render environment settings must hold `KAGGLE_USERNAME` and `KAGGLE_KEY` as secrets. Render generates `MCP_AUTH_TOKEN` from the Blueprint.
- Notebook execution runs arbitrary Python with the server user's permissions. Execute only trusted notebooks.
- Competition submissions require explicit approval for the exact competition and file.

## Local Windows setup
```powershell
cd server
py -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
python server.py
```
Place Kaggle's API token at `%USERPROFILE%\\.kaggle\\kaggle.json`, or set `KAGGLE_USERNAME` and `KAGGLE_KEY` in the environment.

## Render free deployment
1. In Render, choose **New → Blueprint** and select this repository.
2. Render reads `render.yaml` and creates a free Docker web service. The Blueprint does not attach a paid persistent disk.
3. Add `KAGGLE_USERNAME` and `KAGGLE_KEY` in the service's secret environment settings when prompted.
4. Deploy. Health check: `/healthz`; MCP transport: Streamable HTTP.
5. Keep the generated `MCP_AUTH_TOKEN` private and use it as the bearer token when connecting an MCP client.

**Free-plan limitations:** the service may spin down after inactivity and its filesystem is ephemeral. Downloaded datasets and notebooks can be lost on restarts, redeploys, or spin-downs. Free instances have limited memory, CPU, and disk; large Kaggle datasets or long notebook jobs may exceed those limits. Use local Windows mode for large datasets and heavier notebook execution, or upgrade later for persistent storage and always-on hosting.

## CI
GitHub Actions runs on pushes, pull requests, and manual dispatch. It installs dependencies, compiles Python, verifies registered MCP tools, runs the auth middleware tests, and builds the Docker image. It requires no Kaggle credentials.

## MCP tools
- `kaggle_status`
- `search_datasets`, `download_dataset`
- `search_competitions`, `download_competition_data`
- `create_notebook`, `run_notebook`
- `inspect_submission`, `submit_competition_entry`

Kaggle competition rules must be accepted on Kaggle before downloading restricted competition files. The package contains no credentials.
