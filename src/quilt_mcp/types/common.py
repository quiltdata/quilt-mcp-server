"""Shared lightweight type aliases used across modules."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping, TypeAlias

JsonDict: TypeAlias = dict[str, Any]
JsonMap: TypeAlias = Mapping[str, Any]
MutableJsonMap: TypeAlias = MutableMapping[str, Any]
StringMap: TypeAlias = Mapping[str, str]
