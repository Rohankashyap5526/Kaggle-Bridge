"""Kaggle Bridge MCP server: secure Kaggle access, notebook workflows and competitions."""
from __future__ import annotations

import csv
import hmac
import os
import re
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Kaggle Bridge")
BASE_DIR = Path(os.getenv("KAGGLE_BRIDGE_DATA_DIR", Path.home() / "KaggleBridge")).expanduser().resolve()
BASE_DIR.mkdir(parents=True, exist_ok=True)
NOTEBOOK_DIR = BASE_DIR / "notebooks"
NOTEBOOK_DIR.mkdir(parents=True, exist_ok=True)


def _api():
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError as exc:
        raise RuntimeError("Kaggle package is missing. Install requirements.txt first.") from exc
    api = KaggleApi()
    try:
        api.authenticate()
    except Exception as exc:
        raise RuntimeError(
            "Kaggle authentication failed. Configure KAGGLE_USERNAME/KAGGLE_KEY "
            "or ~/.kaggle/kaggle.json. Never paste credentials into chat."
        ) from exc
    return api


def _slug(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
        raise ValueError("Expected a Kaggle owner/name slug.")
    return value


def _competition(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Competition must be its Kaggle URL slug, not a URL.")
    return value


def _safe_name(value: str, suffix: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", value):
        raise ValueError("Use a simple filename without folders or special characters.")
    if not value.endswith(suffix):
        value += suffix
    return value


def _inside_base(path: Path) -> Path:
    resolved = path.resolve()
    if resolved != BASE_DIR and BASE_DIR not in resolved.parents:
        raise ValueError("Path must stay inside the Kaggle Bridge data directory.")
    return resolved


@mcp.tool()
def kaggle_status() -> dict[str, Any]:
    """Check Kaggle API authentication without revealing credentials."""
    _api()
    source = (
        "environment variables"
        if os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY")
        else "Kaggle local configuration"
    )
    return {"authenticated": True, "credential_source": source, "data_root": str(BASE_DIR)}


@mcp.tool()
def search_datasets(query: str, page: int = 1, page_size: int = 20) -> list[dict[str, Any]]:
    """Search public Kaggle datasets by keyword."""
    if not query.strip() or page < 1 or not 1 <= page_size <= 100:
        raise ValueError("Provide a query, page >= 1 and page_size between 1 and 100.")
    rows = _api().dataset_list(search=query.strip(), page=page, page_size=page_size)
    return [
        {
            "ref": getattr(item, "ref", None),
            "title": getattr(item, "title", None),
            "size": getattr(item, "size", None),
            "last_updated": str(getattr(item, "lastUpdated", "")) or None,
            "downloads": getattr(item, "downloadCount", None),
            "url": f"https://www.kaggle.com/datasets/{getattr(item, 'ref', '')}",
        }
        for item in rows
    ]


@mcp.tool()
def download_dataset(dataset: str, subfolder: str = "downloads", unzip: bool = True) -> dict[str, Any]:
    """Download a Kaggle dataset to the configured data directory."""
    ref = _slug(dataset)
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", subfolder) or subfolder.startswith("/") or ".." in Path(subfolder).parts:
        raise ValueError("subfolder must be a safe relative path.")
    target = _inside_base(BASE_DIR / subfolder)
    target.mkdir(parents=True, exist_ok=True)
    _api().dataset_download_files(ref, path=str(target), unzip=unzip, quiet=True)
    return {
        "dataset": ref,
        "directory": str(target),
        "files": [str(path.relative_to(BASE_DIR)) for path in target.rglob("*") if path.is_file()],
    }


@mcp.tool()
def search_competitions(query: str = "", page: int = 1, page_size: int = 20) -> list[dict[str, Any]]:
    """Search Kaggle competitions and return names, reward/deadline metadata where available."""
    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("page must be >= 1 and page_size between 1 and 100.")
    rows = _api().competition_list(search=query.strip() or None, page=page, page_size=page_size)
    result = []
    for item in rows:
        slug = getattr(item, "ref", None) or getattr(item, "url", None)
        result.append(
            {
                "ref": slug,
                "title": getattr(item, "title", None),
                "category": getattr(item, "category", None),
                "reward": getattr(item, "reward", None),
                "deadline": str(getattr(item, "deadline", "")) or None,
                "url": f"https://www.kaggle.com/competitions/{slug}" if slug else None,
            }
        )
    return result


@mcp.tool()
def download_competition_data(competition: str, subfolder: str = "competitions") -> dict[str, Any]:
    """Download competition files. The Kaggle account must have accepted the competition rules."""
    slug = _competition(competition)
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", subfolder) or subfolder.startswith("/") or ".." in Path(subfolder).parts:
        raise ValueError("subfolder must be a safe relative path.")
    target = _inside_base(BASE_DIR / subfolder / slug)
    target.mkdir(parents=True, exist_ok=True)
    _api().competition_download_files(slug, path=str(target), quiet=True)
    return {
        "competition": slug,
        "directory": str(target),
        "files": [str(path.relative_to(BASE_DIR)) for path in target.rglob("*") if path.is_file()],
        "note": "If Kaggle reports rules not accepted, open the competition page and accept its rules first.",
    }


@mcp.tool()
def create_notebook(notebook_name: str, cells: list[dict[str, str]]) -> dict[str, Any]:
    """Create a Jupyter notebook from ordered cells. Each cell has type 'markdown' or 'code' and a source string."""
    try:
        import nbformat
    except ImportError as exc:
        raise RuntimeError("Install notebook dependencies from requirements.txt.") from exc
    name = _safe_name(notebook_name, ".ipynb")
    if not cells or len(cells) > 100:
        raise ValueError("Provide between 1 and 100 notebook cells.")
    notebook = nbformat.v4.new_notebook()
    notebook.cells = []
    for cell in cells:
        kind, source = cell.get("type"), cell.get("source", "")
        if kind not in ("markdown", "code") or not isinstance(source, str) or len(source) > 100_000:
            raise ValueError("Each cell needs type markdown/code and source text up to 100,000 characters.")
        notebook.cells.append(
            nbformat.v4.new_markdown_cell(source)
            if kind == "markdown"
            else nbformat.v4.new_code_cell(source)
        )
    notebook.metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}
    }
    path = _inside_base(NOTEBOOK_DIR / name)
    if path.exists():
        raise FileExistsError("Notebook already exists. Choose another name to avoid overwriting work.")
    nbformat.write(notebook, path)
    return {"notebook": str(path), "cells": len(notebook.cells), "status": "created"}


@mcp.tool()
def run_notebook(notebook_name: str, timeout_seconds: int = 600) -> dict[str, Any]:
    """Execute an existing notebook. Notebook code can access the runtime; run only trusted notebooks."""
    try:
        import nbformat
        from nbclient import NotebookClient
    except ImportError as exc:
        raise RuntimeError("Install notebook dependencies from requirements.txt.") from exc
    name = _safe_name(notebook_name, ".ipynb")
    if not 1 <= timeout_seconds <= 3600:
        raise ValueError("timeout_seconds must be between 1 and 3600.")
    source = _inside_base(NOTEBOOK_DIR / name)
    if not source.is_file():
        raise FileNotFoundError(f"Notebook not found: {name}")
    notebook = nbformat.read(source, as_version=4)
    client = NotebookClient(
        notebook,
        timeout=timeout_seconds,
        kernel_name="python3",
        allow_errors=False,
        resources={"metadata": {"path": str(NOTEBOOK_DIR)}},
    )
    started = time.time()
    try:
        executed = client.execute()
        status, error = "completed", None
    except Exception as exc:
        executed = notebook
        status = "failed"
        error = f"{type(exc).__name__}: {str(exc)[:1500]}"
    output = source.with_name(source.stem + "_executed.ipynb")
    nbformat.write(executed, output)
    summaries = []
    for index, cell in enumerate(executed.cells):
        if cell.cell_type != "code":
            continue
        for item in cell.get("outputs", []):
            if item.output_type == "stream":
                summaries.append({"cell": index, "type": "stream", "text": item.text[:5000]})
            elif item.output_type == "error":
                summaries.append(
                    {
                        "cell": index,
                        "type": "error",
                        "ename": item.ename,
                        "evalue": item.evalue,
                        "traceback": item.get("traceback", [])[-8:],
                    }
                )
            elif item.output_type in ("display_data", "execute_result"):
                data = item.get("data", {})
                summaries.append(
                    {
                        "cell": index,
                        "type": item.output_type,
                        "text": str(data.get("text/plain", ""))[:5000],
                        "has_image": "image/png" in data,
                    }
                )
    return {
        "status": status,
        "executed_notebook": str(output),
        "duration_seconds": round(time.time() - started, 2),
        "outputs": summaries[:100],
        "error": error,
        "security_note": "Notebook code executes with the server process permissions; use only trusted notebooks.",
    }


@mcp.tool()
def inspect_submission(submission_file: str) -> dict[str, Any]:
    """Inspect a CSV submission file stored inside the Kaggle Bridge data directory."""
    name = _safe_name(submission_file, ".csv")
    path = _inside_base(BASE_DIR / name)
    if not path.is_file():
        raise FileNotFoundError("Submission CSV must be placed directly in the Kaggle Bridge data directory.")
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.reader(file)
        header = next(reader, [])
        preview = [row for _, row in zip(range(5), reader)]
    return {
        "file": str(path),
        "columns": header,
        "preview_rows": preview,
        "bytes": path.stat().st_size,
        "next_step": "Verify the competition's required columns and row count before submitting.",
    }


@mcp.tool()
def submit_competition_entry(
    competition: str,
    submission_file: str,
    message: str,
    explicit_confirmation: str = "",
) -> dict[str, Any]:
    """Submit a CSV to Kaggle only after explicit approval for the exact competition and file."""
    slug = _competition(competition)
    name = _safe_name(submission_file, ".csv")
    path = _inside_base(BASE_DIR / name)
    if not path.is_file():
        raise FileNotFoundError("Submission CSV not found in the Kaggle Bridge data directory.")
    if not message.strip() or len(message) > 100:
        raise ValueError("Provide a short submission description (1-100 characters).")
    if explicit_confirmation != "SUBMIT":
        with path.open("r", newline="", encoding="utf-8-sig") as file:
            header = next(csv.reader(file), [])
        return {
            "submitted": False,
            "confirmation_required": True,
            "competition": slug,
            "file": name,
            "columns": header,
            "approval_text": (
                f"To submit {name} to {slug}, the user must explicitly approve this exact action; "
                "then call again with explicit_confirmation='SUBMIT'."
            ),
        }
    result = _api().competition_submit(file_name=str(path), message=message.strip(), competition=slug)
    return {
        "submitted": True,
        "competition": slug,
        "file": name,
        "message": message.strip(),
        "result": str(result),
        "competition_url": f"https://www.kaggle.com/competitions/{slug}",
    }


class _BearerAuthASGI:
    """Protect all MCP HTTP requests with a shared bearer token; expose a minimal health check."""

    def __init__(self, app, token: str):
        self.app = app
        self.token = token.encode("utf-8")

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path") == "/healthz" and scope.get("method") == "GET":
            body = b'{"status":"ok"}'
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        if scope["type"] == "http":
            supplied = next(
                (value for key, value in scope.get("headers", []) if key.lower() == b"authorization"),
                None,
            )
            expected = b"Bearer " + self.token
            if supplied is None or not hmac.compare_digest(supplied, expected):
                body = b'{"error":"unauthorized"}'
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode()),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    if transport == "streamable-http":
        import uvicorn

        token = os.getenv("MCP_AUTH_TOKEN", "")
        if len(token) < 32:
            raise RuntimeError("Set MCP_AUTH_TOKEN to a random secret of at least 32 characters before starting HTTP mode.")
        app = _BearerAuthASGI(mcp.streamable_http_app(), token)
        uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")), proxy_headers=True)
    else:
        mcp.run(transport="stdio")
