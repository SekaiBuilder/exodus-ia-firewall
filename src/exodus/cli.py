"""Exodus command-line interface.

Subcommands:
    exodus serve     # run the local privacy proxy (prints the Exodus banner)
    exodus audit     # inspect the audit trail (what was masked — never the values)
"""
from __future__ import annotations

import argparse
import os
import sys

# Shown in the banner and (matching) in the Claude Code status line.
CLAUDE_LABEL = "Claude v2.1.161"

_ART = r"""
  ███████╗██╗  ██╗ ██████╗ ██████╗ ██╗   ██╗███████╗
  ██╔════╝╚██╗██╔╝██╔═══██╗██╔══██╗██║   ██║██╔════╝
  █████╗   ╚███╔╝ ██║   ██║██║  ██║██║   ██║███████╗
  ██╔══╝   ██╔██╗ ██║   ██║██║  ██║██║   ██║╚════██║
  ███████╗██╔╝ ██╗╚██████╔╝██████╔╝╚██████╔╝███████║
  ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝  ╚═════╝ ╚══════╝"""

_TRUE = {"1", "true", "on", "yes"}


def _paint(code: str, text: str, on: bool) -> str:
    return f"\033[{code}m{text}\033[0m" if on else text


def _print_banner(host: str, port: int) -> None:
    on = sys.stdout.isatty() and not os.getenv("NO_COLOR")
    url = f"http://{host}:{port}"
    local = os.getenv("EXODUS_LOCAL_MODEL", "").lower() in _TRUE
    model = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
    audit = os.getenv("EXODUS_AUDIT_LOG", "audit/exodus.jsonl")
    sep = _paint("90", "  " + "─" * 50, on)

    print(_paint("96;1", _ART, on))
    print()
    print(f"  {_paint('97;1', CLAUDE_LABEL, on)}   {_paint('90', '·', on)}   {_paint('92;1', '🛡  WITH EXODUS', on)}")
    print(f"  {_paint('90', 'privacy router →', on)} {_paint('96', url, on)}")
    print(sep)
    print(f"  🔒  secret firewall   {_paint('92', 'ON', on)}")
    lm = _paint("92", f"ON · {model}", on) if local else _paint("90", "off — firewall only", on)
    print(f"  🧠  local model (M4)  {lm}")
    print(f"  📋  audit trail       {_paint('90', audit, on)}")
    print(sep)
    print(f"  {_paint('90', 'point Claude Code here:', on)}")
    print(f"  {_paint('93', f'export ANTHROPIC_BASE_URL={url}', on)}")
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="exodus",
        description="Sensitivity-aware privacy router for agentic LLM clients.",
    )
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="Run the local privacy proxy.")
    serve.add_argument("--host", default=os.getenv("EXODUS_HOST", "127.0.0.1"))
    serve.add_argument("--port", type=int, default=int(os.getenv("EXODUS_PORT", "8787")))

    audit_cmd = sub.add_parser("audit", help="Inspect the audit trail.")
    audit_cmd.add_argument("--file", default=None, help="Audit log path (default: $EXODUS_AUDIT_LOG)")

    args = parser.parse_args(argv)

    if args.command == "serve":
        import uvicorn

        from exodus.proxy.server import create_app

        _print_banner(args.host, args.port)
        uvicorn.run(create_app(), host=args.host, port=args.port)
        return 0

    if args.command == "audit":
        from exodus.audit import log as audit

        s = audit.summarize(args.file)
        print(f"Exodus audit — {s['path']}")
        print(f"Total acciones: {s['total']}")
        if s["total"]:
            print(f"Por tipo:   {s['by_kind']}")
            print(f"Por acción: {s['by_action']}")
            print("Recientes:")
            for row in s["recent"]:
                print(
                    f"  {row.get('ts', '?')}  {row.get('action', '?'):12} "
                    f"{row.get('kind', '?'):16} (req {row.get('request_id', '?')})"
                )
        else:
            print("(aún no hay nada registrado — usa Exodus y vuelve a mirar)")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
