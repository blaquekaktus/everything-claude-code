# notebooklm-py integration scripts

Bridges Google Drive, Notion, and Slack into a NotebookLM notebook. NotebookLM has no native Notion/Slack connectors, but text and markdown sources are first-class — these scripts pull from each upstream API and hand the content to notebooklm-py as text or Drive sources.

## Install location

Copy the three `.py` files into your local notebooklm-py checkout:

```
~/dev/notebooklm-py/scripts/integrations/
├── drive_to_notebooklm.py
├── notion_to_notebooklm.py
└── slack_to_notebooklm.py
```

## One-liner install (Git Bash)

```bash
cd ~/dev/notebooklm-py
mkdir -p scripts/integrations
BASE=https://raw.githubusercontent.com/blaquekaktus/everything-claude-code/claude/setup-notebooklm-py-a8ovT/notebooklm-integrations
curl -sL $BASE/drive_to_notebooklm.py  -o scripts/integrations/drive_to_notebooklm.py
curl -sL $BASE/notion_to_notebooklm.py -o scripts/integrations/notion_to_notebooklm.py
curl -sL $BASE/slack_to_notebooklm.py  -o scripts/integrations/slack_to_notebooklm.py
```

## Dependencies

With the notebooklm-py venv active:

```bash
pip install google-api-python-client google-auth notion-client slack-sdk aiohttp
```

## Auth setup

| Source | How |
|---|---|
| **Drive** | `gcloud auth application-default login` (one-time) |
| **Notion** | Create integration at https://www.notion.so/my-integrations, share target page/database with it, `export NOTION_TOKEN=secret_...` |
| **Slack** | Create app at https://api.slack.com/apps with bot scopes `channels:history`, `groups:history`, `users:read`; install to workspace; invite bot to channel; `export SLACK_TOKEN=xoxb-...` |

## Usage

```bash
notebooklm login
notebooklm create "My Knowledge Base"
notebooklm list                # copy the notebook ID
NB=<paste_id>

python -m scripts.integrations.drive_to_notebooklm  --notebook $NB --folder <drive_folder_id>
python -m scripts.integrations.notion_to_notebooklm --notebook $NB --database <notion_db_id>
python -m scripts.integrations.slack_to_notebooklm  --notebook $NB --channel C0123456 --days 30

notebooklm ask "Summarize the key themes across these sources"
notebooklm generate audio --wait
```
