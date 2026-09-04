"""Import a Slack channel's history into a NotebookLM notebook as a transcript.

Setup:
    pip install slack-sdk aiohttp
    # 1. Create an app: https://api.slack.com/apps
    # 2. Bot Token Scopes: channels:history, groups:history, users:read,
    #                      channels:read, groups:read
    # 3. Install to workspace, copy the Bot User OAuth Token (xoxb-...)
    # 4. Invite the bot to the channel: /invite @yourbot
    # 5. export SLACK_TOKEN=xoxb-...

Usage:
    python -m scripts.integrations.slack_to_notebooklm \\
        --notebook <NOTEBOOK_ID> --channel C0123456 --days 30
"""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import datetime, timezone

from slack_sdk.web.async_client import AsyncWebClient

from notebooklm import NotebookLMClient


async def _resolve_user(slack: AsyncWebClient, uid: str, cache: dict[str, str]) -> str:
    if uid not in cache:
        try:
            r = await slack.users_info(user=uid)
            cache[uid] = r["user"].get("real_name") or r["user"].get("name") or uid
        except Exception:
            cache[uid] = uid
    return cache[uid]


async def _format_message(slack: AsyncWebClient, m: dict, cache: dict[str, str]) -> str:
    ts = datetime.fromtimestamp(float(m["ts"]), tz=timezone.utc).isoformat(timespec="seconds")
    user = await _resolve_user(slack, m.get("user", "unknown"), cache) if m.get("user") else "(bot)"
    text = m.get("text", "")
    return f"[{ts}] {user}: {text}"


async def _channel_name(slack: AsyncWebClient, channel_id: str) -> str:
    info = await slack.conversations_info(channel=channel_id)
    return info["channel"].get("name", channel_id)


async def fetch_transcript(slack: AsyncWebClient, channel_id: str, days: int) -> str:
    oldest = datetime.now(tz=timezone.utc).timestamp() - days * 86400
    user_cache: dict[str, str] = {}
    lines: list[str] = []
    cursor: str | None = None

    while True:
        resp = await slack.conversations_history(
            channel=channel_id, oldest=str(oldest), limit=200, cursor=cursor
        )
        for m in resp["messages"]:
            lines.append(await _format_message(slack, m, user_cache))
            if m.get("thread_ts") and m["thread_ts"] == m["ts"] and int(m.get("reply_count", 0)) > 0:
                replies = await slack.conversations_replies(channel=channel_id, ts=m["ts"])
                for r in replies["messages"][1:]:
                    lines.append("    " + await _format_message(slack, r, user_cache))

        if not resp.get("has_more"):
            break
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    return "\n".join(reversed(lines))


async def import_channel(notebook_id: str, channel_id: str, days: int) -> None:
    slack = AsyncWebClient(token=os.environ["SLACK_TOKEN"])
    name = await _channel_name(slack, channel_id)
    transcript = await fetch_transcript(slack, channel_id, days)
    if not transcript:
        print(f"skip  #{name}: no messages in last {days}d")
        return
    title = f"Slack #{name} (last {days}d)"
    async with await NotebookLMClient.from_storage() as client:
        await client.sources.add_text(notebook_id, title, transcript, wait=True)
        print(f"ok    {title}: {transcript.count(chr(10)) + 1} lines")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--notebook", required=True, help="NotebookLM notebook ID")
    p.add_argument("--channel", required=True, help="Slack channel ID (e.g. C0123456)")
    p.add_argument("--days", type=int, default=30, help="History window in days (default: 30)")
    args = p.parse_args()
    asyncio.run(import_channel(args.notebook, args.channel, args.days))


if __name__ == "__main__":
    main()
