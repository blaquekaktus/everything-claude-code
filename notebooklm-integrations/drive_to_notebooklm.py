"""Import Google Drive files (or a whole folder) into a NotebookLM notebook.

Setup:
    pip install google-api-python-client google-auth google-auth-oauthlib
    gcloud auth application-default login    # one-time, easiest

Usage:
    python -m scripts.integrations.drive_to_notebooklm \\
        --notebook <NOTEBOOK_ID> --folder <DRIVE_FOLDER_ID>

    python -m scripts.integrations.drive_to_notebooklm \\
        --notebook <NOTEBOOK_ID> --file <DRIVE_FILE_ID>
"""

from __future__ import annotations

import argparse
import asyncio

import google.auth
from googleapiclient.discovery import build

from notebooklm import NotebookLMClient

SUPPORTED_MIMES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
    "application/pdf",
}


def _drive_client():
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/drive.readonly"])
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_folder(folder_id: str) -> list[dict]:
    drive = _drive_client()
    files: list[dict] = []
    page_token = None
    while True:
        resp = drive.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id,name,mimeType)",
            pageSize=1000,
            pageToken=page_token,
        ).execute()
        files.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            return files


def get_file(file_id: str) -> dict:
    return _drive_client().files().get(fileId=file_id, fields="id,name,mimeType").execute()


async def import_files(notebook_id: str, files: list[dict]) -> None:
    async with await NotebookLMClient.from_storage() as client:
        for f in files:
            if f["mimeType"] not in SUPPORTED_MIMES:
                print(f"skip  {f['name']} (unsupported {f['mimeType']})")
                continue
            await client.sources.add_drive(
                notebook_id, f["id"], f["name"], f["mimeType"], wait=True
            )
            print(f"ok    {f['name']}")


async def main_async(args: argparse.Namespace) -> None:
    if args.folder:
        files = list_folder(args.folder)
        print(f"Found {len(files)} files in folder {args.folder}")
    else:
        files = [get_file(args.file)]
    await import_files(args.notebook, files)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--notebook", required=True, help="NotebookLM notebook ID")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--folder", help="Google Drive folder ID")
    g.add_argument("--file", help="Google Drive file ID")
    asyncio.run(main_async(p.parse_args()))


if __name__ == "__main__":
    main()
