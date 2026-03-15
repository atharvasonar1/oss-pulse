"""Parsers for dependency manifest formats used by /analyze."""

from __future__ import annotations

import json
import re


_REQ_NAME_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        normalized = value.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output


def parse_requirements_txt(content: str) -> list[str]:
    packages: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        line = line.split("#", 1)[0].strip()
        line = line.split(";", 1)[0].strip()
        if not line:
            continue

        line = re.split(r"(===|==|~=|!=|>=|<=|>|<)", line, maxsplit=1)[0].strip()
        line = line.split("[", 1)[0].strip()

        match = _REQ_NAME_RE.match(line)
        if match:
            packages.append(match.group(1))

    return _dedupe(packages)


def parse_package_json(content: str) -> list[str]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid package.json content") from exc

    if not isinstance(payload, dict):
        raise ValueError("Invalid package.json content")

    packages: list[str] = []
    for key in ("dependencies", "devDependencies"):
        value = payload.get(key, {})
        if isinstance(value, dict):
            packages.extend(str(name) for name in value.keys())

    return _dedupe(packages)


def parse_go_mod(content: str) -> list[str]:
    packages: list[str] = []
    in_require_block = False

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//"):
            continue

        line = line.split("//", 1)[0].strip()
        if not line:
            continue

        if line.startswith("require ("):
            in_require_block = True
            continue

        if in_require_block and line == ")":
            in_require_block = False
            continue

        if line.startswith("require "):
            line = line[len("require ") :].strip()
            if line.startswith("("):
                in_require_block = True
                continue

            parts = line.split()
            if parts:
                packages.append(parts[0])
            continue

        if in_require_block:
            parts = line.split()
            if parts:
                packages.append(parts[0])

    return _dedupe(packages)
