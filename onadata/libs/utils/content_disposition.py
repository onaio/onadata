# -*- coding: utf-8 -*-
"""
RFC 6266 ``Content-Disposition`` header parsing.

A small, dependency-free port of the subset of ``pyrfc6266`` used by this
codebase to extract a filename from a ``Content-Disposition`` response header
(see :func:`onadata.apps.main.forms.get_filename`). ``pyrfc6266`` is avoided
because it pins ``pyparsing~=3.0.7``, which conflicts with ``httplib2``'s
``pyparsing>=3.1`` requirement.

Only the standard library is used. Behaviour (filename precedence, RFC 5987
extended-value decoding, RFC 2231 continuations, and separator stripping) is
kept identical to ``pyrfc6266.parse_filename``.
"""

import re
from urllib.parse import unquote

# RFC 7230 ``token`` characters (matches the set used by ``pyrfc6266``). ``-`` is
# placed last so it is treated as a literal rather than a range delimiter inside
# the character class.
_TOKEN_RE = re.compile(r"[!#$%&'*+.0-9A-Za-z^_`|~-]+")

# ISO-8859-1 code points that are control characters and therefore invalid in a
# decoded extended value. ``urllib.parse.unquote`` will happily produce these,
# so they are rejected explicitly (as ``pyrfc6266`` does).
_INVALID_ISO8859_1_CHARACTERS = set(
    bytes(list(range(0, 32)) + list(range(127, 160))).decode("iso-8859-1")
)

_SUPPORTED_EXT_CHARSETS = ("utf-8", "iso-8859-1")


class ContentDispositionError(ValueError):
    """Raised when a ``Content-Disposition`` header cannot be parsed."""


def secure_filename(filename: str) -> str:
    """Replace path separators so the filename cannot traverse directories.

    Args:
        filename: A potentially unsafe filename.

    Returns:
        The filename with ``\\`` and ``/`` replaced by ``_``.
    """
    return filename.replace("\\", "_").replace("/", "_")


def _scan_params(header: str) -> "list[tuple[str, str, bool]]":
    """Tokenise a ``Content-Disposition`` header into its parameters.

    Args:
        header: The raw header value.

    Returns:
        A list of ``(name, value, is_quoted)`` tuples in header order, where
        ``name`` is lower-cased and ``is_quoted`` indicates the value came from
        a quoted-string rather than a bare token.

    Raises:
        ContentDispositionError: If the header does not begin with a
            disposition-type token or a parameter is malformed.
    """
    index, length = 0, len(header)

    def skip_whitespace() -> None:
        nonlocal index
        while index < length and header[index] in " \t":
            index += 1

    skip_whitespace()
    match = _TOKEN_RE.match(header, index)
    if not match:
        raise ContentDispositionError("missing disposition-type")
    index = match.end()

    params: "list[tuple[str, str, bool]]" = []
    while True:
        skip_whitespace()
        if index >= length:
            break
        if header[index] != ";":
            raise ContentDispositionError(f"expected ';' at position {index}")
        index += 1
        skip_whitespace()
        if index >= length:
            break

        match = _TOKEN_RE.match(header, index)
        if not match:
            raise ContentDispositionError(f"invalid parameter name at {index}")
        name = match.group(0).lower()
        index = match.end()

        skip_whitespace()
        if index >= length or header[index] != "=":
            raise ContentDispositionError("expected '=' after parameter name")
        index += 1
        skip_whitespace()

        if index < length and header[index] == '"':
            index += 1
            buffer: "list[str]" = []
            while index < length:
                char = header[index]
                if char == "\\" and index + 1 < length:
                    buffer.append(header[index + 1])
                    index += 2
                    continue
                if char == '"':
                    index += 1
                    break
                buffer.append(char)
                index += 1
            params.append((name, "".join(buffer), True))
        else:
            match = _TOKEN_RE.match(header, index)
            if not match:
                raise ContentDispositionError("invalid parameter value")
            params.append((name, match.group(0), False))
            index = match.end()

    return params


def _decode_ext_value(raw: str) -> str:
    """Decode an RFC 5987 extended value (``charset'lang'percent-encoded``).

    Args:
        raw: The raw parameter value.

    Returns:
        The decoded string.

    Raises:
        ContentDispositionError: If the value is malformed, uses an unsupported
            charset, or decodes to invalid bytes.
    """
    parts = raw.split("'", 2)
    if len(parts) != 3:
        raise ContentDispositionError("malformed extended value")
    charset = (parts[0] or "utf-8").lower()
    if charset not in _SUPPORTED_EXT_CHARSETS:
        raise ContentDispositionError(f"unsupported charset: {charset}")
    try:
        value = unquote(parts[2], encoding=charset, errors="strict")
    except UnicodeDecodeError as error:
        raise ContentDispositionError("invalid encoding in extended value") from error
    if charset == "iso-8859-1" and (set(value) & _INVALID_ISO8859_1_CHARACTERS):
        raise ContentDispositionError("invalid encoding in extended value")
    return value


def parse_filename(header: str) -> "str | None":
    """Return a safe filename from a ``Content-Disposition`` header.

    Mirrors ``pyrfc6266.parse_filename``: the RFC 6266 ``filename*`` (extended)
    form takes precedence over plain ``filename``, RFC 2231 continuations
    (``filename*0``/``filename*1`` …) are concatenated, and the result is passed
    through :func:`secure_filename`.

    Args:
        header: The raw ``Content-Disposition`` header value.

    Returns:
        The decoded filename, or ``None`` if the header carries no filename.

    Raises:
        ContentDispositionError: If the header cannot be parsed or a parameter
            is malformed.
    """
    decoded: "dict[str, str]" = {}
    for name, raw, is_quoted in _scan_params(header):
        if name in decoded:
            raise ContentDispositionError(f"duplicate parameter: {name}")
        # A parameter whose name ends with ``*`` carries an extended value,
        # unless it was given as a quoted-string (which is never extended).
        if name.endswith("*") and not is_quoted:
            decoded[name] = _decode_ext_value(raw)
        else:
            decoded[name] = raw

    def combine(start: str) -> str:
        filename = decoded[start]
        for idx in range(1, 99999):
            for key in (f"filename*{idx}*", f"filename*{idx}"):
                if key in decoded:
                    filename += decoded[key]
                    break
            else:
                break
        return filename

    for key in ("filename*", "filename", "filename*0*", "filename*0"):
        if decoded.get(key):
            filename = combine(key) if key.startswith("filename*0") else decoded[key]
            if filename:
                return secure_filename(filename)

    return None
