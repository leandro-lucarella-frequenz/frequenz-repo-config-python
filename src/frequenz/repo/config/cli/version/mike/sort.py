# License: MIT
# Copyright © 2023 Frequenz Energy-as-a-Service GmbH

"""Sort `mike`'s `version.json` file with a custom order."""


import dataclasses
import json
import sys
from typing import TextIO

from .... import github
from ....mkdocs.mike import MikeVersionInfo, sort_mike_versions


def _sort(stream_in: TextIO, stream_out: TextIO) -> None:
    """Sort the versions in the given in stream to the given out stream.

    Args:
        stream_in: The stream to read the versions from.
        stream_out: The stream to write the sorted versions to.
    """
    versions = json.load(stream_in)
    sorted_versions = sort_mike_versions([MikeVersionInfo(**v) for v in versions])
    json.dump(sorted_versions, stream_out, separators=(",", ":"))


def _load_and_sort_versions_from(stream: TextIO) -> list[MikeVersionInfo]:
    """Load the versions from the given stream.

    Args:
        stream: The stream to read the versions from.

    Returns:
        The loaded versions.
    """
    versions = [MikeVersionInfo(**v) for v in json.load(stream)]
    return sort_mike_versions(versions)


def _dump_versions_to(versions: list[MikeVersionInfo], stream: TextIO) -> None:
    """Dump the versions to the given stream.

    Args:
        versions: The versions to dump.
        stream: The stream to write the versions to.
    """
    json.dump([dataclasses.asdict(v) for v in versions], stream, separators=(",", ":"))


def main() -> None:
    """Sort `mike`'s `version.json` file with a custom order.

    The versions are sorted using `sort_versions()`.

    If no arguments are given, then the contents are read from stdin and the sorted
    versions are printed to stdout.

    If one argument is given, then the contents of the file are replaced with the sorted
    versions.

    If more than one argument is given, then an error is printed to stderr and the
    program exits with a non-zero exit code.
    """
    github.configure_logging()

    match len(sys.argv):
        case 1:
            _dump_versions_to(_load_and_sort_versions_from(sys.stdin), sys.stdout)
        case 2:
            with open(sys.argv[1], "r", encoding="utf8") as stream_in:
                versions = _load_and_sort_versions_from(stream_in)
            with open(sys.argv[1], "w", encoding="utf8") as stream_out:
                _dump_versions_to(versions, stream_out)

        case _:
            print(
                f"""\
Usage: {sys.argv[0]} [<versions.json>]

If <versions.json> is given, the contents will be replaced with the sorted versions.
Otherwise, the contents are read from stdin and the sorted versions are printed to stdout.
""",
                file=sys.stderr,
            )
            sys.exit(2)


if __name__ == "__main__":
    main()
