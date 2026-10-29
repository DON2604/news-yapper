"""Operational commands:

uv run python -m app.cli seed-demo          # idempotent DEMO content + source registry
uv run python -m app.cli seed-sources       # source registry only (safe in production)
uv run python -m app.cli grant-admin <email>
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.db import session_scope
from app.models import User
from app.seed.sources import seed_sources


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed-demo", help="Insert clearly labelled DEMO content (idempotent)")
    sub.add_parser("seed-sources", help="Insert/update the source registry")
    grant = sub.add_parser("grant-admin", help="Give an existing user the admin role")
    grant.add_argument("email")
    args = parser.parse_args(argv)

    if args.command == "seed-sources":
        with session_scope() as db:
            count = seed_sources(db)
        print(f"Source registry ready ({count} sources).")
        return 0

    if args.command == "seed-demo":
        from app.seed.demo import seed_demo

        with session_scope() as db:
            seed_sources(db)
            summary = seed_demo(db)
        print("Demo content ready:", ", ".join(f"{k}={v}" for k, v in summary.items()))
        return 0

    if args.command == "grant-admin":
        with session_scope() as db:
            user = db.scalar(select(User).where(User.email == args.email.strip().lower()))
            if user is None:
                print("No user with that e-mail has signed in yet.", file=sys.stderr)
                return 1
            user.is_admin = True
        print(f"{args.email} is now an admin.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
