"""Official TOON 4.4 encoding fixtures; provenance is in fixtures/README.md."""

import json
from pathlib import Path

import pytest

from monarch_cli.output.toon import encode

CASES = [
    json.loads(line)
    for line in (Path(__file__).parent / "fixtures/toon-4.4.jsonl").read_text().split("\n")
    if line
]


@pytest.mark.parametrize("case", CASES, ids=[f"{case['source']}:{case['index']}" for case in CASES])
def test_official_encoding_fixture(case):
    options = case.get("options", {})
    kwargs = {"delimiter": options.get("delimiter", ","), "indent": options.get("indentSize", 2)}
    if case.get("shouldError"):
        with pytest.raises(ValueError):
            encode(case["input"], **kwargs)
    else:
        assert encode(case["input"], **kwargs) == case["expected"]
