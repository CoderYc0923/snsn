from __future__ import annotations

import argparse
import os

import uvicorn

from app.config import get_settings


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def cmd_dev(args: argparse.Namespace) -> None:
    """Local development: reload app/ only, bind loopback by default."""
    host = args.host or os.environ.get("SNSN_HOST") or "127.0.0.1"
    port = args.port if args.port is not None else _env_int("SNSN_PORT", 8001)
    print(f"[snsn] dev  http://{host}:{port}  (reload=app/)")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=True,
        reload_dirs=["app"],
    )


def cmd_start(args: argparse.Namespace) -> None:
    """Production-like: no reload; host/port/workers from settings or flags."""
    settings = get_settings()
    host = args.host or settings.host
    port = args.port if args.port is not None else settings.port
    workers = args.workers if args.workers is not None else settings.workers
    print(f"[snsn] start http://{host}:{port}  workers={workers}")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        workers=workers,
        reload=False,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="snsn-api",
        description="SnSn API process entry (dev / start)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    dev = sub.add_parser("dev", help="Hot-reload for local development")
    dev.add_argument("--host", default=None)
    dev.add_argument("--port", type=int, default=None)
    dev.set_defaults(func=cmd_dev)

    start = sub.add_parser("start", help="No reload; for systemd / production")
    start.add_argument("--host", default=None)
    start.add_argument("--port", type=int, default=None)
    start.add_argument("--workers", type=int, default=None)
    start.set_defaults(func=cmd_start)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
