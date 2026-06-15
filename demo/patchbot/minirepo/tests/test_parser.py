from parser import parse_csv_line, parse_int


def test_parse_int_basic():
    assert parse_int("42") == 42


def test_parse_int_negative():
    assert parse_int(" -7 ") == -7


def test_csv_line():
    assert parse_csv_line("1,2,3") == [1, 2, 3]


def test_csv_line_with_spaces():
    assert parse_csv_line(" 4 , 5 ") == [4, 5]
