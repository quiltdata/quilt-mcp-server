#!/usr/bin/env python3
"""Generate a test JWT for local development."""

from __future__ import annotations

import argparse
import json
import time
from typing import Any, Dict

import jwt


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an HS256 JWT for testing.")
    parser.add_argument("--id", required=True, help="User id claim.")
    parser.add_argument("--uuid", required=True, help="User uuid claim.")
    parser.add_argument("--secret", default="dev-secret", help="HS256 shared secret.")
    parser.add_argument("--expires-in", type=int, default=3600, help="Expiration in seconds.")
    parser.add_argument("--issuer", help="Issuer (iss) claim.")
    parser.add_argument("--audience", help="Audience (aud) claim.")
    parser.add_argument(
        "--extra-claims",
        default="{}",
        help="Additional JSON claims to merge into the payload.",
    )

    args = parser.parse_args()

    payload: Dict[str, Any] = {
        "id": args.id,
        "uuid": args.uuid,
        "exp": int(time.time()) + int(args.expires_in),
    }

    if args.issuer:
        payload["iss"] = args.issuer
    if args.audience:
        payload["aud"] = args.audience

    extra_claims = json.loads(args.extra_claims)
    if not isinstance(extra_claims, dict):
        raise ValueError("--extra-claims must be a JSON object.")
    payload.update(extra_claims)

    token = jwt.encode(payload, args.secret, algorithm="HS256")
    print(token)


if __name__ == "__main__":
    main()
