"""Check mootdx/TDX HQ server connectivity.

Usage:
    python scripts/check_tdx.py
    python scripts/check_tdx.py --limit 20 --symbol 002405
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tradingagents.dataflows.a_stock import (  # noqa: E402
    _parse_tdx_server,
    _tcp_reachable,
    _tdx_socket_timeout,
    _tdx_server_candidates,
    _tdx_timeout,
)


def _probe(server: tuple[str, int], symbol: str, timeout: int) -> tuple[bool, str]:
    from mootdx.quotes import Quotes

    client = None
    try:
        client = Quotes.factory(market="std", server=server, timeout=timeout)
        df = client.bars(symbol=symbol, frequency=9, offset=2)
        if df is None or df.empty:
            return False, "connected but returned empty bars"
        return True, f"{len(df)} rows"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe TDX HQ servers used by mootdx.")
    parser.add_argument("--symbol", default="000001", help="6-digit A-share code to probe")
    parser.add_argument("--limit", type=int, default=38, help="max server candidates to test")
    parser.add_argument("--timeout", type=int, default=_tdx_timeout(), help="socket timeout seconds")
    parser.add_argument(
        "--socket-timeout",
        type=float,
        default=_tdx_socket_timeout(),
        help="fast TCP precheck timeout seconds",
    )
    args = parser.parse_args()

    servers = _tdx_server_candidates()
    pinned = _parse_tdx_server(os.environ.get("TRADINGAGENTS_TDX_SERVER"))
    if pinned and pinned in servers:
        servers = [pinned] + [item for item in servers if item != pinned]

    print(
        f"Testing TDX servers for symbol {args.symbol}, "
        f"socket_timeout={args.socket_timeout}s, mootdx_timeout={args.timeout}s"
    )
    print("Set TRADINGAGENTS_TDX_SERVER=ip:port to pin a working server.\n")

    ok_count = 0
    for index, server in enumerate(servers[: args.limit], start=1):
        if not _tcp_reachable(server, timeout=args.socket_timeout):
            print(f"{index:02d}. {server[0]}:{server[1]}  FAIL  TCP closed/timeout")
            continue
        ok, msg = _probe(server, args.symbol, args.timeout)
        status = "OK" if ok else "FAIL"
        print(f"{index:02d}. {server[0]}:{server[1]}  {status}  {msg}")
        if ok:
            ok_count += 1

    print(f"\nWorking servers: {ok_count}/{min(args.limit, len(servers))}")
    return 0 if ok_count else 1


if __name__ == "__main__":
    raise SystemExit(main())
