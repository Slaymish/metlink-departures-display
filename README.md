# Metlink Departures Display

Glanceable “LED sign” display (web + CLI) for Metlink bus departures in Wellington.

## Setup

1. Create a `.env` file (you can copy from `.env.example`):

   - `METLINK_API_KEY=...your key...`
   - Optional: set defaults for your house:
     - `METLINK_STOP_ID=7958`
     - `METLINK_LIMIT=2`
     - `METLINK_PORT=8765`
     - `METLINK_REFRESH_SECONDS=15`

2. Make scripts executable (once):

   - `chmod +x bus-times bus_times.py`

## Quickstart

- Run the web sign:
  - `python3 bus_sign_server.py`
  - Open `http://localhost:8765/`

- Run the terminal sign:
  - `./bus-times`

## Usage

- Default stop (7958), next two departures:
  - `./bus-times`

- Another stop id:
  - `./bus-times 1234`

- Pick interactively (lists all stops, then choose a number):
  - `./bus-times pick`

- Pick interactively with a filter (less scrolling):
  - `./bus-times pick brooklyn`

You can also run the legacy wrapper:
- `./get\ stops`

## Always-on display (living room / by the door)

Two simple options:

1) Fullscreen terminal on a small screen (Raspberry Pi / mini PC)

- Run:
  - `watch -n 15 ./bus-times`

2) Share over your home network (good for old phones, e-ink, ESP32, etc)

- Start the server:
  - `./bus_sign_server.py`
- From any device on your LAN (full-screen “LED sign” page):
  - `http://<host>:8765/`
- Plain text endpoint (good for microcontrollers / e-ink renderers):
  - `http://<host>:8765/sign.txt`

## Run on boot (Raspberry Pi / mini PC)

- Copy and edit the example unit:
  - `sudo cp homebustimes.service.example /etc/systemd/system/homebustimes.service`
- Update paths + `User=` inside it to match your device.
- Enable:
  - `sudo systemctl daemon-reload`
  - `sudo systemctl enable --now homebustimes`

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
