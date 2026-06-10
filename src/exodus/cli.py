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

    upstream = os.getenv("EXODUS_UPSTREAM", "").lower()
    is_openai = "openai" in upstream
    client_label = "Codex (OpenAI)" if is_openai else CLAUDE_LABEL
    env_var = "OPENAI_BASE_URL" if is_openai else "ANTHROPIC_BASE_URL"
    client_hint = "point Codex here:" if is_openai else "point Claude Code here:"

    print(_paint("96;1", _ART, on))
    print()
    print(f"  {_paint('97;1', client_label, on)}   {_paint('90', '·', on)}   {_paint('92;1', '🛡  WITH EXODUS', on)}")
    print(f"  {_paint('90', 'privacy router →', on)} {_paint('96', url, on)}")
    print(sep)
    print(f"  🔒  secret firewall   {_paint('92', 'ON', on)}")
    lm = _paint("92", f"ON · {model}", on) if local else _paint("90", "off — firewall only", on)
    print(f"  🧠  local model       {lm}")
    print(f"  📋  audit trail       {_paint('90', audit, on)}")
    print(sep)
    print(f"  {_paint('90', client_hint, on)}")
    print(f"  {_paint('93', f'export {env_var}={url}', on)}")
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

    sub.add_parser("selftest", help="Run the masking self-test over every detector kind.")

    verify_cmd = sub.add_parser("verify", help="Verify a running proxy's attestation.")
    verify_cmd.add_argument("--url", default="http://127.0.0.1:8787", help="Proxy base URL.")
    verify_cmd.add_argument("--mrenclave", default=None, help="Pin an expected MRENCLAVE (hex).")
    verify_cmd.add_argument(
        "--allow-simulated",
        action="store_true",
        help="Accept simulated documents (development without SGX hardware).",
    )

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

    if args.command == "selftest":
        from exodus.selftest import main as run_selftest

        return run_selftest()

    if args.command == "verify":
        from exodus.verify import verify_url

        v = verify_url(args.url, args.mrenclave, args.allow_simulated)
        print(f"Exodus attestation — {args.url}  (tee: {v.tee})")
        for line in v.checks:
            print(f"  ✓ {line}")
        for line in v.failures:
            print(f"  ✗ {line}")
        if v.mr_enclave:
            print(f"  MRENCLAVE: {v.mr_enclave}")
            print(f"  MRSIGNER:  {v.mr_signer}")
        print(f"VERDICT: {'TRUSTED' if v.trusted else 'NOT TRUSTED'}")
        return 0 if v.trusted else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
