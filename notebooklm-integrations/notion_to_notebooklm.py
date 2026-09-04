"""Import Notion pages or a whole database into a NotebookLM notebook.

Setup:
    pip install notion-client
    # 1. Create an integration: https://www.notion.so/my-integrations
    # 2. Share the target page/database with your integration
    # 3. export NOTION_TOKEN=secret_...

Usage:
    python -m scripts.integrations.notion_to_notebooklm \\
        --notebook <NOTEBOOK_ID> --page <NOTION_PAGE_ID>

    python -m scripts.integrations.notion_to_notebooklm \\
        --notebook <NOTEBOOK_ID> --database <NOTION_DB_ID>
"""

from __future__ import annotations

import argparse
import asyncio
import os

from notion_client import AsyncClient as Notion

from notebooklm import NotebookLMClient


def _rich_text(rt: list[dict]) -> str:
    return "".join(item.get("plain_text", "") for item in rt)


async def _blocks_to_md(notion: Notion, block_id: str, depth: int = 0) -> str:
    out: list[str] = []
    cursor: str | None = None
    while True:
        resp = await notion.blocks.children.list(block_id=block_id, start_cursor=cursor)
        for b in resp["results"]:
            t = b["type"]
            data = b[t]
            indent = "  " * depth
            if t == "paragraph":
                out.append(indent + _rich_text(data["rich_text"]))
            elif t in ("heading_1", "heading_2", "heading_3"):
                level = int(t.split("_")[1])
                out.append(f"{'#' * level} {_rich_text(data['rich_text'])}")
            elif t == "bulleted_list_item":
                out.append(f"{indent}- {_rich_text(data['rich_text'])}")
            elif t == "numbered_list_item":
                out.append(f"{indent}1. {_rich_text(data['rich_text'])}")
            elif t == "to_do":
                mark = "x" if data.get("checked") else " "
                out.append(f"{indent}- [{mark}] {_rich_text(data['rich_text'])}")
            elif t in ("quote", "callout"):
                out.append(f"> {_rich_text(data['rich_text'])}")
            elif t == "code":
                lang = data.get("language", "")
                out.append(f"```{lang}\n{_rich_text(data['rich_text'])}\n```")
            elif t == "divider":
                out.append("---")
            elif t == "toggle":
                out.append(f"{indent}- {_rich_text(data['rich_text'])}")
            else:
                text = _rich_text(data.get("rich_text", []))
                if text:
                    out.append(indent + text)

            if b.get("has_children"):
                child_md = await _blocks_to_md(notion, b["id"], depth + 1)
                if child_md:
                    out.append(child_md)

        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return "\n".join(out)


def _page_title(page: dict) -> str:
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            return _rich_text(prop["title"]) or "Untitled"
    return "Untitled"


async def import_page(notebook_id: str, page_id: str, notion: Notion | None = None) -> None:
    notion = notion or Notion(auth=os.environ["NOTION_TOKEN"])
    page = await notion.pages.retrieve(page_id)
    title = _page_title(page)
    md = await _blocks_to_md(notion, page_id)
    async with await NotebookLMClient.from_storage() as client:
        await client.sources.add_text(notebook_id, title, md or "(empty page)", wait=True)
        print(f"ok    {title}")


async def import_database(notebook_id: str, database_id: str) -> None:
    notion = Notion(auth=os.environ["NOTION_TOKEN"])
    cursor: str | None = None
    while True:
        resp = await notion.databases.query(database_id=database_id, start_cursor=cursor)
        for page in resp["results"]:
            await import_page(notebook_id, page["id"], notion)
        if not resp.get("has_more"):
            return
        cursor = resp.get("next_cursor")


async def main_async(args: argparse.Namespace) -> None:
    if args.page:
        await import_page(args.notebook, args.page)
    else:
        await import_database(args.notebook, args.database)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--notebook", required=True, help="NotebookLM notebook ID")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--page", help="Notion page ID")
    g.add_argument("--database", help="Notion database ID")
    asyncio.run(main_async(p.parse_args()))


if __name__ == "__main__":
    main()
