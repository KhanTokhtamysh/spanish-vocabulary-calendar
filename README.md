# Spanish Vocabulary Calendar

Notion is the source of truth for vocabulary. GitHub generates and hosts a rolling Apple Calendar (.ics) feed.

## Flow

Notion → GitHub Actions → `docs/spanish-vocabulary.ics` → GitHub Pages → iPhone / Apple Watch

## Notion data source

`55ef2eed-c99a-44a1-8973-fcd1f918eb1f`

New entries are included automatically. Tick **Exclude from Calendar** to omit an item without deleting it.

## Exposure stages

No retention feedback is required. Calendar presentation is based on the age of each item:

- 0–2 days: Spanish — English
- 3–13 days: Spanish — ?
- 14–44 days: English → ?
- 45+ days: English → ? (maintenance frequency)

These are exposure stages, not claims about memory.

## Calendar defaults

- Europe/Madrid
- 30-day rolling feed
- 08:00–23:00
- 15-minute events every 15 minutes
- no alerts
- transparent/free
- deterministic stable UIDs
- examples/forms in DESCRIPTION

## One-time setup

1. Create a Notion integration with read access and share the **Spanish Vocabulary** database with it.
2. Add the integration token to this repository as an Actions secret named `NOTION_TOKEN`.
3. In **Settings → Pages**, choose **Deploy from a branch**, branch `main`, folder `/docs`.
4. Run **Actions → Update vocabulary calendar → Run workflow** once.

Calendar subscription URL:

`https://khantokhtamysh.github.io/spanish-vocabulary-calendar/spanish-vocabulary.ics`
