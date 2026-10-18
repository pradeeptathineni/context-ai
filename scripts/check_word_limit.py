#!/usr/bin/env python3

# scripts/check_word_limit.py - Check the actual UTF-8 deliverable without changing it


import argparse
import hashlib
import json
from pathlib import Path
import sys


def inspect(data, limit, exclusive):
    """Count the whole artifact and bind the result to its exact bytes.

    Args:
        data: Complete UTF-8 artifact bytes.
        limit: Nonnegative word bound.
        exclusive: Require fewer words instead of allowing the bound itself.

    Returns:
        Count, byte digest and whether the bound passed.

    Raises:
        UnicodeDecodeError: The artifact is not valid UTF-8.
    """
    words = len(data.decode("utf-8").split())
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "words": words,
        "counting": "Python Unicode whitespace split; whole artifact",
        "comparison": "lt" if exclusive else "le",
        "limit": limit,
        "passed": words < limit if exclusive else words <= limit,
    }


def main():
    """Check the saved artifact and print a JSON receipt.

    Returns:
        Exit status: 0 for a pass, 1 for excess words, or 2 for invalid input.
    """
    parser = argparse.ArgumentParser(
        description="Check the complete UTF-8 artifact against an explicit word limit."
    )
    parser.add_argument("artifact", type=Path)
    bounds = parser.add_mutually_exclusive_group(required=True)
    bounds.add_argument("--max-words", type=int, help="at most N words")
    bounds.add_argument("--under-words", type=int, help="strictly fewer than N words")
    args = parser.parse_args()
    limit = args.max_words if args.max_words is not None else args.under_words
    if limit < 0:
        parser.error("word limit must be nonnegative")
    # Check the saved bytes without rewriting the deliverable
    try:
        result = inspect(args.artifact.read_bytes(), limit, args.under_words is not None)
    except (OSError, UnicodeError) as error:
        print(f"Cannot check artifact: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
