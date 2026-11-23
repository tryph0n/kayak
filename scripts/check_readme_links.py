"""Check that the repository paths cited in Markdown files exist.

Usage, from the repository root:

    python scripts/check_readme_links.py [PATH ...] [--allow PATTERN]...
        [--skip PATTERN]...

PATH is a Markdown file, or a directory (every tracked ``*.md`` under it).
Without PATH, the ``files`` config key is used, else ``README.md``.

Optional config in ``pyproject.toml``, table ``[tool.check-readme-links]``,
with the list keys ``files``, ``allow`` and ``skip``. Command-line values are
added to the config values.

The tracked set comes from ``git ls-files``. Checked: Markdown links, images,
reference definitions, HTML ``href`` and ``src`` attributes, and inline code
spans that look like a repository path. Fenced code blocks and HTML comments
are ignored.

Exit code: 0 if nothing is missing, 1 if a reference is missing, 2 on a usage
or environment error.
"""

from __future__ import annotations

import argparse
import fnmatch
import posixpath
import re
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import unquote

try:
    import tomllib
except ImportError:  # Python 3.10
    tomllib = None

CONFIG_TABLE = "check-readme-links"
CONFIG_KEYS = ("files", "allow", "skip")

REFDEF_RE = re.compile(r"^\s{0,3}\[(?!\^)[^\]]+\]:\s*(<[^>]*>|\S+)")
HTML_ATTR_RE = re.compile(
    r"""(?:^|(?<=\s))(?:href|src)\s*=\s*["']([^"']*)["']""", re.IGNORECASE
)
FENCE_RE = re.compile(r"^[\s>]*(`{3,}|~{3,})(.*)$")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
LINE_SUFFIX_RE = re.compile(r":\d+(?:-\d+)?$")
ANCHOR_SUFFIX_RE = re.compile(r"#\S*$")
QUOTE_PREFIX_RE = re.compile(r"^(?:\s*>)+")
MASK_RE = re.compile(r"\x00(\d+)\x00")
TITLE_CLOSE = {'"': '"', "'": "'", "(": ")"}

PATH_EXTENSIONS = (
    ".py",
    ".md",
    ".yaml",
    ".yml",
    ".toml",
    ".json",
    ".csv",
    ".ipynb",
    ".sql",
    ".txt",
    ".sh",
    ".cfg",
    ".ini",
    ".lock",
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".html",
    ".parquet",
    ".template",
    ".example",
)
PATH_NAMES = {
    "Dockerfile",
    "Makefile",
    "LICENSE",
    ".gitignore",
    ".python-version",
    ".dockerignore",
}
FORBIDDEN_CHARS = set("<>{}()[]=@,;'\"|`")
FORBIDDEN_START = ("/", "~", "$", "-")


class UsageError(Exception):
    """An error that ends the run with exit code 2."""


def load_config() -> dict[str, list[str]]:
    if tomllib is None:
        print(
            "warning: tomllib is not available; pyproject.toml config is ignored",
            file=sys.stderr,
        )
        return {}
    pyproject = Path("pyproject.toml")
    if not pyproject.is_file():
        return {}
    try:
        with pyproject.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise UsageError(f"cannot read pyproject.toml: {exc}") from exc
    tool = data.get("tool", {})
    table = tool.get(CONFIG_TABLE, {}) if isinstance(tool, dict) else {}
    if not isinstance(table, dict):
        raise UsageError(f"pyproject.toml: [tool.{CONFIG_TABLE}] must be a table")
    for key in table:
        if key not in CONFIG_KEYS:
            print(
                f"warning: pyproject.toml: unknown key '{key}' in "
                f"[tool.{CONFIG_TABLE}] is ignored",
                file=sys.stderr,
            )
    config: dict[str, list[str]] = {}
    for key in CONFIG_KEYS:
        value = table.get(key, [])
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise UsageError(
                f"pyproject.toml: [tool.{CONFIG_TABLE}] '{key}' must be a list "
                "of strings"
            )
        config[key] = value
    return config


def check_repo_root() -> None:
    """Fail when the current folder is inside the repository, not at its root."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-prefix"],
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return
    if result.stdout.decode("utf-8", "replace").strip():
        raise UsageError("run this script from the repository root")


def tracked_paths() -> tuple[set[str], set[str], list[str]]:
    """Return tracked paths with parent folders, the folders, and tracked files."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise UsageError(f"cannot run 'git ls-files' here: {exc}") from exc
    files = [p for p in result.stdout.decode("utf-8", "replace").split("\0") if p]
    paths = {"."}
    dirs = {"."}
    for name in files:
        parts = name.split("/")
        for i in range(1, len(parts) + 1):
            paths.add("/".join(parts[:i]))
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))
    return paths, dirs, files


def matches_pattern(pattern: str, candidate: str) -> bool:
    if fnmatch.fnmatchcase(candidate, pattern):
        return True
    if pattern.endswith("/"):
        return (
            candidate.startswith(pattern)
            or candidate + "/" == pattern
            or fnmatch.fnmatchcase(candidate, pattern + "*")
        )
    return False


def is_allowed(allow: list[str], raw: str, candidates: list[str]) -> bool:
    texts = [raw, *candidates]
    return any(matches_pattern(p, t) for p in allow for t in texts)


def find_closing_run(line: str, start: int, size: int) -> tuple[int, int] | None:
    """Find the next run of exactly ``size`` backticks at or after ``start``."""
    pos = start
    while True:
        first = line.find("`", pos)
        if first == -1:
            return None
        last = first
        while last < len(line) and line[last] == "`":
            last += 1
        if last - first == size:
            return first, last
        pos = last


def scan_line(line: str, in_comment: bool) -> tuple[str, list[str], bool]:
    """Remove HTML comments and mask inline code spans.

    Code spans are found first: a ``<!--`` inside a span does not open a
    comment. Each span is replaced by a ``\\x00N\\x00`` token and returned in
    the list. Return the masked line, the spans and the comment state.
    """
    out: list[str] = []
    spans: list[str] = []
    pos = 0
    while pos < len(line):
        if in_comment:
            end = line.find("-->", pos)
            if end == -1:
                break
            in_comment = False
            pos = end + 3
            out.append(" ")
            continue
        comment = line.find("<!--", pos)
        tick = line.find("`", pos)
        if tick == -1 and comment == -1:
            out.append(line[pos:])
            break
        if comment != -1 and (tick == -1 or comment < tick):
            out.append(line[pos:comment])
            in_comment = True
            pos = comment + 4
            continue
        size = 0
        while tick + size < len(line) and line[tick + size] == "`":
            size += 1
        closing = find_closing_run(line, tick + size, size)
        if closing is None:
            out.append(line[pos : tick + size])
            pos = tick + size
            continue
        out.append(line[pos:tick])
        out.append(f"\x00{len(spans)}\x00")
        spans.append(line[tick + size : closing[0]].strip())
        pos = closing[1]
    return "".join(out), spans, in_comment


def iter_lines(text: str) -> Iterator[tuple[int, str, list[str]]]:
    """Yield (line number, masked line, code spans), skipping fences."""
    fence_marker = ""
    in_comment = False
    for number, line in enumerate(text.splitlines(), start=1):
        if not in_comment:
            match = FENCE_RE.match(line)
            if fence_marker:
                if (
                    match
                    and match.group(1)[0] == fence_marker[0]
                    and len(match.group(1)) >= len(fence_marker)
                    and not match.group(2).strip()
                ):
                    fence_marker = ""
                continue
            if match and not (match.group(1)[0] == "`" and "`" in match.group(2)):
                fence_marker = match.group(1)
                continue
        masked, spans, in_comment = scan_line(line, in_comment)
        yield number, masked, spans


def match_bracket(line: str, start: int) -> int | None:
    """Return the index of the ``]`` that closes the ``[`` at ``start``."""
    depth = 0
    pos = start
    while pos < len(line):
        char = line[pos]
        if char == "\\":
            pos += 2
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return pos
        pos += 1
    return None


def parse_target(line: str, pos: int) -> tuple[str, int] | None:
    """Parse ``target "title")`` after a ``(``; return the target and the end."""
    size = len(line)
    while pos < size and line[pos] in " \t":
        pos += 1
    if pos >= size:
        return None
    if line[pos] == "<":
        end = line.find(">", pos)
        if end == -1:
            return None
        target = line[pos + 1 : end]
        pos = end + 1
    else:
        start = pos
        depth = 0
        while pos < size:
            char = line[pos]
            if char == "\\":
                pos += 2
                continue
            if char.isspace():
                break
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
            pos += 1
        target = line[start : min(pos, size)]
    while pos < size and line[pos] in " \t":
        pos += 1
    if pos < size and line[pos] == ")":
        return target, pos + 1
    if pos < size and line[pos] in TITLE_CLOSE:
        end = line.find(TITLE_CLOSE[line[pos]], pos + 1)
        if end != -1:
            pos = end + 1
            while pos < size and line[pos] in " \t":
                pos += 1
            if pos < size and line[pos] == ")":
                return target, pos + 1
    end = line.find(")", pos)
    if end == -1:
        return None
    return target, end + 1


def find_links(line: str) -> list[tuple[str, str]]:
    """Return (text, target) for each inline link or image, nested ones too."""
    found: list[tuple[str, str]] = []
    pos = 0
    while pos < len(line):
        if line[pos] == "\\":
            pos += 2
            continue
        if line[pos] == "[":
            end = match_bracket(line, pos)
            if end is not None and line[end + 1 : end + 2] == "(":
                parsed = parse_target(line, end + 2)
                if parsed:
                    text = line[pos + 1 : end]
                    found.append((text, parsed[0]))
                    found.extend(find_links(text))
                    pos = parsed[1]
                    continue
        pos += 1
    return found


def clean_target(target: str) -> str:
    target = target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    target = target.split("#", 1)[0].split("?", 1)[0]
    return unquote(target)


class Checker:
    def __init__(self, allow: list[str]) -> None:
        self.allow = allow
        self.paths, self.dirs, self.files = tracked_paths()
        self.base_names = {p.rsplit("/", 1)[-1] for p in self.paths}
        self.checked = 0
        self.missing = 0

    def looks_like_path(self, span: str, md_dir: str) -> bool:
        if not span or any(c.isspace() for c in span) or "://" in span:
            return False
        if span.startswith(FORBIDDEN_START) or FORBIDDEN_CHARS & set(span):
            return False
        if ":" in span or span.rsplit("/", 1)[-1] == ".env":
            return False
        if span in PATH_NAMES or span.lower().endswith(PATH_EXTENSIONS):
            return True
        if "/" not in span:
            return False
        first = span.split("/", 1)[0]
        return posixpath.normpath(posixpath.join(md_dir, first)) in self.paths or (
            first in self.paths
        )

    def exists(self, path: str, md_dir: str, from_root_too: bool) -> bool:
        """Return True if ``path`` exists in the tracked set."""
        bare = path.rstrip("/")
        if not bare:
            return True
        pool = self.dirs if path.endswith("/") else self.paths
        roots = [md_dir]
        if from_root_too and md_dir != "":
            roots.append("")
        is_glob = "*" in bare or "?" in bare
        for base in roots:
            joined = posixpath.normpath(posixpath.join(base, bare))
            if joined == ".." or joined.startswith("../"):
                continue
            if is_glob:
                if any(fnmatch.fnmatchcase(p, joined) for p in pool):
                    return True
            elif joined in pool:
                return True
        return (
            from_root_too
            and not is_glob
            and "/" not in path
            and bare in self.base_names
        )

    def candidates(self, path: str, md_dir: str, from_root_too: bool) -> list[str]:
        bare = path.rstrip("/")
        found = []
        for base in [md_dir, ""] if from_root_too else [md_dir]:
            joined = posixpath.normpath(posixpath.join(base, bare))
            found.append(joined)
            if path.endswith("/"):
                found.append(joined + "/")
        return found

    def check_one(
        self, md: str, line_no: int, raw: str, path: str, kind: str, root_only: bool
    ) -> None:
        md_dir = posixpath.dirname(md)
        from_root_too = kind == "code"
        if root_only:
            md_dir = ""
        self.checked += 1
        if is_allowed(self.allow, raw, self.candidates(path, md_dir, from_root_too)):
            return
        if self.exists(path, md_dir, from_root_too):
            return
        self.missing += 1
        print(f"{md}:{line_no}: missing '{raw}' ({kind})")

    def check_file(self, md: str) -> None:
        try:
            text = Path(md).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise UsageError(f"cannot read {md}: {exc}") from exc
        md_dir = posixpath.dirname(md)
        for line_no, line, spans in iter_lines(text):
            exempt: set[int] = set()
            targets = []
            for link_text, target in find_links(line):
                whole = MASK_RE.fullmatch(link_text.strip())
                if whole and SCHEME_RE.match(clean_inner(target)):
                    exempt.add(int(whole.group(1)))
                targets.append(target)
            ref = REFDEF_RE.match(QUOTE_PREFIX_RE.sub("", line))
            if ref:
                targets.append(ref.group(1))
            targets.extend(m.group(1) for m in HTML_ATTR_RE.finditer(line))
            for target in targets:
                self.check_link(md, line_no, target)
            for index, raw_span in enumerate(spans):
                span = LINE_SUFFIX_RE.sub("", ANCHOR_SUFFIX_RE.sub("", raw_span))
                if index not in exempt and self.looks_like_path(span, md_dir):
                    self.check_one(md, line_no, span, span, "code", False)

    def check_link(self, md: str, line_no: int, target: str) -> None:
        stripped = clean_inner(target)
        if "\x00" in stripped:
            return
        if not stripped or stripped.startswith(("#", "//")):
            return
        if SCHEME_RE.match(stripped):
            return
        path = clean_target(stripped)
        if not path:
            return
        root_only = path.startswith("/")
        if root_only:
            path = path.lstrip("/")
            if not path:
                return
        self.check_one(md, line_no, stripped, path, "link", root_only)


def clean_inner(target: str) -> str:
    """Strip blanks and one pair of angle brackets from a raw link target."""
    stripped = target.strip()
    if stripped.startswith("<") and stripped.endswith(">"):
        stripped = stripped[1:-1].strip()
    return stripped


def collect_markdown(paths: list[str], skip: list[str], files: list[str]) -> list[str]:
    selected: list[str] = []
    for arg in paths:
        path = Path(arg)
        if path.is_dir():
            prefix = posixpath.normpath(path.as_posix())
            for name in files:
                if name.lower().endswith(".md") and (
                    prefix == "." or name.startswith(prefix + "/")
                ):
                    selected.append(name)
        elif path.is_file():
            selected.append(posixpath.normpath(path.as_posix()))
        else:
            raise UsageError(f"file not found: {arg}")
    unique = list(dict.fromkeys(selected))
    return [m for m in unique if not any(matches_pattern(p, m) for p in skip)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that repository paths cited in Markdown files exist."
    )
    parser.add_argument("paths", nargs="*", metavar="PATH")
    parser.add_argument("--allow", action="append", default=[], metavar="PATTERN")
    parser.add_argument("--skip", action="append", default=[], metavar="PATTERN")
    args = parser.parse_args(argv)
    try:
        check_repo_root()
        config = load_config()
        allow = config.get("allow", []) + args.allow
        skip = config.get("skip", []) + args.skip
        targets = args.paths or config.get("files") or ["README.md"]
        checker = Checker(allow)
        markdown = collect_markdown(targets, skip, checker.files)
        for md in markdown:
            checker.check_file(md)
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(
        f"{checker.checked} references checked in {len(markdown)} files, "
        f"{checker.missing} missing"
    )
    return 1 if checker.missing else 0


if __name__ == "__main__":
    sys.exit(main())
