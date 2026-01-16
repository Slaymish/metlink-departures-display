# Contributing

Thanks for wanting to improve Metlink Departures Display.

## What’s in scope

- Bug fixes
- Output formatting improvements (terminal + web sign)
- Better stop picking/search
- Raspberry Pi / always-on reliability improvements

Please keep the UX focused on “glanceable next departures”.

## Local setup

1. Create `.env` from `.env.example` and set `METLINK_API_KEY`.
2. Run the CLI:
   - `./bus-times`
3. Run the server:
   - `python3 bus_sign_server.py`
   - Open `http://localhost:8765/`

## Submitting changes

- Keep changes small and easy to review.
- Prefer the standard library (this project intentionally has no dependencies).
- Update `README.md` if you change usage/config.
- If you add new config keys, also update `.env.example`.

## Coding style

- Python 3.10+ syntax is used (type hints, `| None`, etc).
- Keep functions small and names descriptive.

## Reporting issues

When filing a bug, please include:

- What you expected vs what happened
- The command you ran
- Your stop id (and whether you’re using `pick`)
- The raw API error text if present

## Security

- Do not commit `.env`.
- Treat `METLINK_API_KEY` like a secret.
