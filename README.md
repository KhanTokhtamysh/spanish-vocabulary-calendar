# Spanish Vocabulary Calendar

Notion is the source of truth for vocabulary. GitHub Actions generates and publishes a rolling Apple Calendar (`.ics`) feed.

## Flow

Notion → GitHub Actions → GitHub Pages → iPhone / Apple Watch

## Notion data source

`55ef2eed-c99a-44a1-8973-fcd1f918eb1f`

New entries are included automatically. Tick **Exclude from Calendar** to omit an item without deleting it.

## Exposure stages

No retention feedback is required. Calendar presentation is based on the age of each item:

- 0–2 days: `Spanish — English`
- 3–13 days: `Spanish — ?`
- 14–44 days: `English → ?`
- 45+ days: `English → ?` at maintenance frequency

These are exposure stages, not claims about actual memory.

## Calendar defaults

- Europe/Madrid
- 30-day rolling feed
- 08:00–23:00
- 15-minute events every 15 minutes
- no alerts
- transparent/free
- deterministic stable UIDs
- examples and conjugation/forms in DESCRIPTION

## One-time setup

1. In the Notion Developer portal, create a **Personal access token** with the **Notion API** capability for your workspace.
2. Copy the token when Notion shows it.
3. In this repository, open **Settings → Secrets and variables → Actions**.
4. Add a repository secret named `NOTION_TOKEN` containing that token.
5. Open **Settings → Pages**.
6. Under **Build and deployment → Source**, select **GitHub Actions**.
7. Open **Actions → Update vocabulary calendar → Run workflow**.

A Notion personal access token uses your own page permissions, so the vocabulary database does not need to be separately shared with a bot connection.

The workflow also refreshes automatically every six hours.

## Calendar subscription

Once Pages has deployed successfully:

`https://khantokhtamysh.github.io/spanish-vocabulary-calendar/spanish-vocabulary.ics`

On iPhone: **Calendar → Calendars → Add Calendar → Add Subscription Calendar**, then paste the URL.

## Repository structure

- `generator/generate_calendar.py` — queries Notion and generates the ICS feed.
- `.github/workflows/update-calendar.yml` — scheduled/manual Pages deployment.
- `site/index.html` — simple landing page deployed alongside the feed.

The Notion token is never stored in repository files.
