#!/usr/bin/env python3

from __future__ import annotations

import argparse
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import bus_times


class Handler(BaseHTTPRequestHandler):
    server_version = "HomeBusTimes/1.0"

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path not in ("/", "/sign.txt"):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b"Not found\n")
            return

        cfg = self.server.cfg  # type: ignore[attr-defined]

        api_key = bus_times._get_api_key()
        if not api_key:
            body = (
                "Missing METLINK_API_KEY.\n"
                "Set it as an env var, or create a .env in this folder with:\n"
                "  METLINK_API_KEY=...your key...\n"
            )
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
            return

        try:
            payload = bus_times.fetch_predictions(
                api_key=api_key,
                stop_id=str(cfg.stop_id),
                limit=int(cfg.limit),
            )
            stop_label, views = bus_times.to_views(payload)
            text = bus_times.render_sign_text(
                stop_label=stop_label,
                stop_id=str(cfg.stop_id),
                views=views,
                limit=int(cfg.limit),
                styled=False,
            )
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write((f"Error: {e}\n").encode("utf-8"))
            return

        if path == "/sign.txt":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write((text + "\n").encode("utf-8"))
            return

        refresh = int(getattr(cfg, "refresh", 15) or 15)
        pre = escape(text)
        html = f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <meta http-equiv=\"refresh\" content=\"{refresh}\" />
    <title>Bus Times</title>
    <style>
      html, body {{ height: 100%; }}
      body {{
        margin: 0;
        background: #000;
        color: #ffb000;
        display: flex;
        align-items: center;
        justify-content: center;
      }}
      pre {{
        margin: 0;
        padding: 2.5vh 3vw;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        font-weight: 700;
        font-size: clamp(20px, 6vw, 90px);
        line-height: 1.05;
        white-space: pre;
      }}
    </style>
  </head>
  <body>
    <pre>{pre}</pre>
  </body>
</html>"""

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, fmt: str, *args: object) -> None:
        # quiet by default; comment out to enable request logs
        return


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Serve the bus sign output over HTTP.")
    parser.add_argument("--stop-id", default=bus_times._get_default_stop_id(), help="Metlink stop id")
    parser.add_argument("--limit", type=int, default=bus_times._get_default_limit(), help="Departures to show")
    parser.add_argument("--bind", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument(
        "--port",
        type=int,
        default=int(bus_times._get_setting("METLINK_PORT") or 8765),
        help="Port (default: 8765 or METLINK_PORT)",
    )
    parser.add_argument(
        "--refresh",
        type=int,
        default=int(bus_times._get_setting("METLINK_REFRESH_SECONDS") or 15),
        help="HTML refresh seconds (default: 15 or METLINK_REFRESH_SECONDS)",
    )
    args = parser.parse_args(argv)

    httpd = ThreadingHTTPServer((args.bind, int(args.port)), Handler)
    httpd.cfg = args  # type: ignore[attr-defined]

    print(f"Serving sign at http://{args.bind}:{args.port}/")
    print(f"Text endpoint:  http://{args.bind}:{args.port}/sign.txt")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
