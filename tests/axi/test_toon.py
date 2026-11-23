"""TOON 4.4 encoder conformance examples, including structural edge cases."""

from datetime import datetime

import pytest

from monarch_cli.output.toon import encode


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({}, ""),
        ([], "[]"),
        (None, "null"),
        (False, "false"),
        ({"name": "Coffee shop", "amount": -3.5}, "name: Coffee shop\namount: -3.5"),
        ({"values": [1, True, None, "05"]}, 'values[4]: 1,true,null,"05"'),
        ({"values": []}, "values: []"),
        ([{"id": "1", "name": "A"}, {"name": "B", "id": "2"}], '[2]{id,name}:\n  "1",A\n  "2",B'),
        (
            [
                {"id": 1, "owner": {"name": "A", "active": True}},
                {"id": 2, "owner": {"active": False, "name": "B"}},
            ],
            "[2]{id,owner{name,active}}:\n  1,A,true\n  2,B,false",
        ),
        (
            {"accounts": {"a": {"balance": 1}, "b": {"balance": 2}}},
            "accounts[2:]{balance}:\n  a: 1\n  b: 2",
        ),
        ({"a": {"id": 1}, "b": {"id": 2}}, "[2:]{id}:\n  a: 1\n  b: 2"),
        ([{}, {"id": 1}], "[2]:\n  -\n  - id: 1"),
        (
            [{"nested": {"id": 1}, "name": "A"}, 3],
            "[2]:\n  - nested:\n      id: 1\n    name: A\n  - 3",
        ),
        ([[{"id": 1}, {"id": 2}]], "[1]:\n  - [2]:\n    - id: 1\n    - id: 2"),
        ([[1, "two"], [], "three"], "[3]:\n  - [2]: 1,two\n  - [0]:\n  - three"),
        ({"a-b": "true", "汉字": "你好 👋"}, '"a-b": "true"\n"汉字": 你好 👋'),
        ({"special": 'x\b\f\x00\n\r\t"\\'}, 'special: "x\\u0008\\u000c\\u0000\\n\\r\\t\\"\\\\"'),
        ([0.0, -0.0, 1.0, 0.000001, 1e20], "[5]: 0,0,1,0.000001,100000000000000000000"),
        ([float("nan"), float("inf"), float("-inf")], "[3]: null,null,null"),
        ({"date": datetime(2026, 11, 19, 10, 30)}, 'date: "2026-11-19T10:30:00"'),
    ],
)
def test_spec_examples(value, expected):
    assert encode(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "true",
        "false",
        "null",
        "42",
        "05",
        "+1",
        "1E-6",
        " leading",
        "trailing ",
        "-start",
        "#comment",
        "x:y",
        "x,y",
        "[value]",
        "{value}",
        "\ufeffroot",
    ],
)
def test_required_quoting(value):
    assert encode(value).startswith('"')


@pytest.mark.parametrize("value", ["\ud800", {"key": "\udfff"}, {"\ud800": 1}])
def test_surrogates_are_rejected(value):
    with pytest.raises(ValueError, match="surrogate"):
        encode(value)


def test_cycles_are_rejected():
    value = []
    value.append(value)
    with pytest.raises(ValueError, match="circular"):
        encode(value)
