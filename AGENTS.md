# Repository Guidelines

## Project Structure & Data
- Core app lives in `flaskapp.py`; HTML templates sit in `templates/`.
- Persistent artifacts: `youtube_cache/` (per-video folders with `data.json` and downloaded media) and `favorites.json`.
- Runtime SSL material in `certs/` (self-signed by `entrypoint.sh` if absent); transient HTTP cache under `/tmp/r.cache`.

## Build, Run, and Common Commands
- Install deps: `pip install -r requirements.txt` (Python 3.10+ recommended).
- Local dev server: `python flaskapp.py` (listens on `0.0.0.0:5002`; debug unless `FLASK_ENV=production`).
- Docker workflow: `docker-compose up --build` (mounts repo into `/app`, preserves `certs/`).
- Clear request cache only: POST to `/clear-cache` or delete `/tmp/r.cache*`.

## Coding Style & Naming
- Python style: 4-space indents, prefer small helpers over long route handlers. Favor descriptive variable names and early returns for error cases.
- Templates: keep HTML minimal, no JS; reuse existing structure in `templates/youtube*.html`, `templates/index.html`.
- Files stored under `youtube_cache/` follow `{video_id}/data.json` and `{video_id}_{format_id}.<ext>`; keep that convention.
- Logging: use `logzero.logger` for app logs; avoid print except debug scaffolding you later remove.

## Testing Expectations
- No formal test suite yet; add targeted tests if you introduce complex parsing or caching logic.
- Manual checks: `python flaskapp.py`, then exercise `/`, `/youtube?q=`, `/youtube?video=` flows, favorites add/remove, and transcript fetch.
- If touching caching or file writes, validate `youtube_cache/` contents and request cache regeneration.

## Commit & PR Guidelines
- Commits: concise present-tense subjects (e.g., `Add transcript fetch fallback`, `Tighten URL rewrite rules`); group logical changes.
- PRs should explain motivation, key changes, and manual verification steps. Include notes on cache impacts (`youtube_cache/`, `/tmp/r.cache`) and any new external commands (e.g., `yt-dlp` flags).
- Link related issues where possible; add screenshots or short notes only when UI output changes.

## Security & Configuration Notes
- HTTPS: dev certs auto-generated in `certs/`; for production, mount real certs and set `FLASK_ENV=production`.
- Network calls disable SSL verification for proxying; avoid introducing credentials into logs or cached HTML.
- Respect filesystem targets: keep writes inside `youtube_cache/`, `favorites.json`, and `/tmp/r.cache*`; avoid storing secrets in the repo.
