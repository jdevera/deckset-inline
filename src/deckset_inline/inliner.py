#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
-------------------------------------------
A filter to include other files in markdown
-------------------------------------------

<!-- <inline src="path" verbatim lang="python" start="2" end="12"> -->
CONTENT
<!-- </inline> -->

After filtering, anything between the opening and closing directives will be
replaced.

These are the attributes:

 - src: The path of the file to include
 - verbatim: Wrap the included content in ``` (verbatim takes no value)
 - lang: Specify this as the verbatim block language (implies verbatim)
 - start: The first line of the file to include (1 by default)
 - end: The last line of the file to include (last line by default)

"""

import argparse
import collections
import enum
import fileinput
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from itertools import islice
from pathlib import Path
from typing import Optional, Union, Iterator, Generator

from . import VERSION

COMMENT_RE = re.compile(r"^\s*<!--\s*(.*?)\s*-->")


class InlineError(Exception):
    def __init__(self, message, line, lineno):
        self.line = line
        self.lineno = lineno
        super().__init__(f"Line {lineno}: {message}\n{line}")


class TagType(enum.Enum):
    OPENING = enum.auto()
    CLOSING = enum.auto()


@dataclass
class InlineDirective:
    """
    Inliner directive entity.

    Takes care of storing all attributes specified in a directive, as well as where it is found in the source file. It
    validates those attributes, and generates the contents to appear between opening and closing directive lines.
    """
    type: TagType
    lineno: int
    line: str = field(repr=False)
    source: Optional[Union[Path, str]] = None
    verbatim: Optional[bool] = True
    lang: Optional[str] = None
    start: Optional[int] = None
    end: Optional[int] = None

    def __post_init__(self):
        """
        Validate all parsed attributes of the directive.
        """
        if self.type != TagType.OPENING:
            return

        self.validate_source()

        if self.start is not None:
            try:
                self.start = int(self.start)
            except ValueError:
                self.raise_error(f"Invalid value {self.start} for start attribute")
        if self.end is not None:
            try:
                self.end = int(self.end)
            except ValueError:
                self.raise_error(f"Invalid value {self.end} for end attribute")

    def validate_source(self):
        if self.source is None:
            self.raise_error("Source attribute must be present in directive")
        if not isinstance(self.source, str):
            self.raise_error(f"Invalid type {type(self.source)} for source attribute")
        self.source = Path(self.source)
        if not self.source.exists():
            self.raise_error(f"File {self.source} not found")
        try:
            with self.source.open("r"):
                pass
        except Exception as ex:
            self.raise_error(str(ex))

    def contents(self) -> Generator[str, None, None]:
        """
        Generate all the lines, reading from the source file, that will fill up this directive block.
        """
        start = self.start - 1 if self.start is not None else 0
        end = self.end if self.end is not None else None
        if self.verbatim:
            lang = "" if self.lang is None else self.lang
            yield f"```{lang}\n"

        with self.source.open("r") as fin:
            yield from islice(fin, start, end)
        if self.verbatim:
            yield "```\n"

    def raise_error(self, msg: str):
        """
        A convenience method to raise errors when validating.
        """
        raise InlineError(msg, self.line, self.lineno)


def consume_iterator(iterator: Iterator) -> None:
    """
    Go though all the elements of an iterator. Especially useful to consume generators.
    """

    # feed the entire iterator into a zero-length deque
    collections.deque(iterator, maxlen=0)


def extract_line_comment(line: str) -> Optional[str]:
    """
    Remove the comment markers from a commented HTML line and return the uncommented results
    :param line: The line content.
    :return: Uncommented line, or None if this was not a comment.
    """
    if (match := COMMENT_RE.match(line)) is not None:
        return match.group(1)
    return None


class DirectiveParser(HTMLParser):
    """
    Extremely simple HTML parser that parses a single tag and will accept any tag name.
    """
    def __init__(self):
        super().__init__()
        self.tag = None
        self.attrs = None

    def handle_starttag(self, tag, attrs):
        assert self.tag is None
        self.tag = tag
        self.attrs = attrs

    def error(self, message):
        raise Exception(message)


def parse_directive(line: str, lineno: int) -> Optional[InlineDirective]:
    """
    Parse a possible inliner directive in a line and return an InlineDirective object with the parameters from it,
    or None if not found.

    :param line: The line contents where to look for a directive.
    :param lineno: the line number of the passed in line (for error reporting)
    :return: An InlineDirective object, which can be opening or closing,
             or None if the line did not contain a directive.
    """

    # If the line was a comment, get the uncommented content, otherwise bail out, this was not a directive
    directive = extract_line_comment(line)
    if directive is None:
        return None

    # Another early check before we try to parse the content as XML. Does this look like one of our opening directives?
    if re.search(r"^<(inline|python) ", directive) is not None:
        # Parse the directive XML and return an InlineDirective object with its parameters
        parser = DirectiveParser()
        parser.feed(directive)
        attrs = dict(parser.attrs)
        if "src" not in attrs:
            raise InlineError(
                f"Attribute 'src' not set for {parser.tag} directive", line, lineno
            )
        src = attrs["src"]
        if parser.tag == "python":
            verbatim = True
            lang = "python"
        elif parser.tag == "inline":
            # The presence of the lang attribute implies verbatim
            verbatim = "verbatim" in attrs or "lang" in attrs
            lang = attrs.get("lang")
        start = attrs.get("start")
        end = attrs.get("end")
        return InlineDirective(
            type=TagType.OPENING,
            lineno=lineno,
            line=line,
            source=src,
            verbatim=verbatim,
            lang=lang,
            start=start,
            end=end,
        )

    if directive in ("</inline>", "</python>"):
        # If this looks like a closing directive, then return the closing InlineDirective object.
        return InlineDirective(type=TagType.CLOSING, lineno=lineno, line=line)


def result_generator(input_lines: Iterator[str] = sys.stdin, clean=False):
    """
    Go line by line of the input and place them in the output. If a directive is found, replace all input
    lines between the opening and closing directive tags with the results of executing the directive.

    When running on `clean` mode, the space between directive opening and closing tags is left empty.

    :param input_lines: An iterator of lines taken as input
    :param clean: Flag indicating whether to clean the output
    :return: A generator or resulting lines with the file contents either included or cleared
    """
    current_directive = None

    for lineno, line in enumerate(input_lines, 1):
        # Lines outside of directives remain untouched:
        if current_directive is None:
            yield line

        if (directive := parse_directive(line, lineno)) is not None:
            if directive.type == TagType.OPENING:
                if current_directive is not None:
                    raise InlineError(
                        f"New directive found while previous is still open at line {current_directive.lineno}",
                        line,
                        lineno,
                    )
                current_directive = directive
                if not clean:
                    yield from directive.contents()
            else:
                yield line
                current_directive = None
    if current_directive is not None:
        raise InlineError(
            "Directive not closed at end of file",
            current_directive.line,
            current_directive.lineno,
        )


def check(input_lines: Iterator[str], clean: bool) -> None:
    """
    Pass through the whole file without applying any changes just to ensure there are no errors with the directives.

    These could com from opening a directive without closing the one before, or from reaching the end of the file
    without having found the closing tag for one that was open.

    :param input_lines: An iterator of the lines to process.
    :param clean: A flag that determines whether we are cleaning or not (if not cleaning, then we are inlining).
    :return: Nothing
    :raises: InlineError in case of errors in the source file.
    """
    consume_iterator(result_generator(input_lines, clean))


def inline(input_lines: Iterator[str] = sys.stdin, clean: bool = False):
    """
    Go through each input line in `input_lines` and execute any inliner directive that is found according to the value
    of the `clean` flag. Write the result to stdout, which will likely be redirected higher in the call stack.

    :param input_lines: An iterator of the lines to process.
    :param clean: A flag that determines whether we are cleaning or not (if not cleaning, then we are inlining).
    :return: Nothing
    :raises: InlineError in case of errors in the source file.
    """
    for line in result_generator(input_lines, clean):
        sys.stdout.write(line)


def parse_args(argv):
    """ Parse and validate command line arguments """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("input", default="-", nargs="?", help="Input files (use - for stdin)")
    parser.add_argument("--in-place", "-i", action="store_true", help="Modify input files in place")
    parser.add_argument("--backup-ext", "-b", default="", help="The extension for backup files (when in-place)")
    parser.add_argument("--clean", "-c", action="store_true", help="Remove all inlined contents")
    parser.add_argument("--version", action='version', version=f"%(prog)s {VERSION}")
    args = parser.parse_args(argv[1:])

    if args.in_place and args.input == "-":
        parser.error("When using --in-place or -i, standard input is not a valid input")
    if args.backup_ext and not args.in_place:
        parser.error("--backup-ext or -b only make sense when --in-place or -i is used")
    return args


def main(argv=None):
    """ Run this program """
    if argv is None:
        argv = sys.argv
    args = parse_args(argv)
    try:
        # When reading from files, do a check before changing anything
        if args.input != "-":
            with open(args.input, "r") as fin:
                check(fin, args.clean)

        with fileinput.input(
            files=(args.input,), inplace=args.in_place, backup=args.backup_ext
        ) as fin:
            inline(fin, args.clean)

    except KeyboardInterrupt:
        sys.exit(-1)


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
