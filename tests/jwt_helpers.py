#!/usr/bin/env python3
"""JWT fixture helpers for tests.

These helpers load the real catalog JWT fixture and do not generate tokens.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "data" / "sample-catalog-jwt.json"
_EXPIRED_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "data" / "sample-catalog-jwt-expired.json"
_MISSING_EXP_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "data" / "sample-catalog-jwt-missing-exp.json"
_EXTRA_CLAIM_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "data" / "sample-catalog-jwt-extra-claim.json"


def load_sample_catalog_jwt() -> Dict[str, Any]:
    with _FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def get_sample_catalog_token() -> str:
    return load_sample_catalog_jwt()["token"]


def get_sample_catalog_claims() -> Dict[str, Any]:
    return load_sample_catalog_jwt()["payload"]


def get_expired_catalog_token() -> str:
    with _EXPIRED_FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)["token"]


def get_missing_exp_catalog_token() -> str:
    with _MISSING_EXP_FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)["token"]


def get_extra_claim_catalog_token() -> str:
    with _EXTRA_CLAIM_FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)["token"]


if __name__ == "__main__":
    print(get_sample_catalog_token())
