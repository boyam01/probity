"""A tiny CSV-of-integers parser. One real bug lives in parse_csv_line."""


def parse_int(token):
    """Parse a decimal integer token, allowing surrounding whitespace."""
    token = token.strip()
    sign = 1
    if token.startswith("-"):
        sign = -1
        token = token[1:]
    if not token.isdigit():
        raise ValueError(f"invalid integer: {token!r}")
    return sign * int(token)


def parse_csv_line(line):
    """Parse one comma-separated line of integers."""
    return [parse_int(part) for part in line.split(";")]
