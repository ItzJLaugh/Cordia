#!/usr/bin/env python3
"""Cordia language / compiler integration.

NOT IMPLEMENTED IN MVP. EXTENSION POINT ONLY.

The long-term direction is that an interface definition compiles to a Cordia
program rather than being interpreted as a prompt. The MVP keeps the definition
declarative and JSON-shaped precisely so that becomes possible without a
rewrite: nothing in the definition encodes *how* a step runs, only what it is.

`futureHooks.cordiaCompilerCompatible` on each saved definition marks the ones
written under that constraint.

    def compile(definition: dict) -> str
"""

from __future__ import annotations


def available() -> bool:
    return False


def compile_definition(definition):
    raise NotImplementedError(
        "Cordia compiler integration is an extension point, not implemented in the MVP.")
