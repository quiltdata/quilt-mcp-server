#!/usr/bin/env python3
"""Generate a test JWT for local development."""

from __future__ import annotations

import argparse
import json
import time
from typing import Any, Dict

import jwt


def _parse_session_tags(values: list[str]) -> Dict[str, str]:
    tags: Dict[str, str] = {}
    for raw in values:
        for pair in raw.split(","):
            if not pair:
                continue
            if "=" not in pair:
                raise ValueError(f"Invalid session tag '{pair}'. Use key=value format.")
            key, value = pair.split("=", 1)
            tags[key.strip()] = value.strip()
    return tags


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an HS256 JWT for testing.")
    parser.add_argument("--sub", required=True, help="Subject claim (user identifier).")
    parser.add_argument("--secret", default="dev-secret", help="HS256 shared secret.")
    parser.add_argument("--expires-in", type=int, default=3600, help="Expiration in seconds.")
    parser.add_argument("--issuer", help="Issuer (iss) claim.")
    parser.add_argument("--audience", help="Audience (aud) claim.")
    parser.add_argument("--role-arn", help="Role ARN for STS AssumeRole.")
    parser.add_argument(
        "--session-tag",
        action="append",
        default=[],
        help="Session tag(s) in key=value format. Repeat or comma-separate.",
    )
    parser.add_argument(
        "--transitive-tag-keys",
        default="",
        help="Comma-separated list of transitive tag keys.",
    )
    parser.add_argument(
        "--extra-claims",
        default="{}",
        help="Additional JSON claims to merge into the payload.",
    )

    args = parser.parse_args()

    payload: Dict[str, Any] = {
        "sub": args.sub,
        "exp": int(time.time()) + int(args.expires_in),
    }

    if args.issuer:
        payload["iss"] = args.issuer
    if args.audience:
        payload["aud"] = args.audience
    if args.role_arn:
        payload["role_arn"] = args.role_arn

    if args.session_tag:
        payload["session_tags"] = _parse_session_tags(args.session_tag)

    if args.transitive_tag_keys:
        payload["transitive_tag_keys"] = [key for key in args.transitive_tag_keys.split(",") if key]

    extra_claims = json.loads(args.extra_claims)
    if not isinstance(extra_claims, dict):
        raise ValueError("--extra-claims must be a JSON object.")
    payload.update(extra_claims)

    token = jwt.encode(payload, args.secret, algorithm="HS256")
    print(token)


if __name__ == "__main__":
    main()
