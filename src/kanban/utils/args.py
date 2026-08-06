"""
Helpers that read values off a parsed argparse Namespace.

Shared by the CLI and REPL command handlers, which parse the same arguments
with different parsers.
"""

import argparse

from ..models import Priority


def parse_priority(args: argparse.Namespace) -> Priority | None:
    """Return the --priority argument as a Priority, or None if not provided."""
    priority = args.priority
    return Priority(priority) if priority else None
