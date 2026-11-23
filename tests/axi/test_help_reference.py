"""Every public help reference is complete, local, and has parseable examples."""

import re
import shlex

import click
import pytest
from typer.main import get_command
from typer.testing import CliRunner

from monarch_cli.main import app


def public_commands():
    found = []

    def walk(command, words):
        if command.hidden:
            return
        found.append((tuple(words), command))
        if isinstance(command, click.Group):
            for name, child in command.commands.items():
                walk(child, [*words, name])

    walk(get_command(app), [])
    return found


@pytest.mark.parametrize(
    "words,command",
    public_commands(),
    ids=lambda x: " ".join(x) if isinstance(x, tuple) else x.name,
)
def test_each_help_has_complete_reference_and_examples(words, command, tmp_path):
    result = CliRunner().invoke(
        app, [*words, "--help"], color=False, env={"COLUMNS": "220", "TERM": "dumb"}
    )
    assert result.exit_code == 0, result.output
    # Help stays human-readable. Data and errors have their own TOON boundary.
    assert "Usage:" in result.stdout
    assert "Examples:" in result.stdout
    assert "<object object at" not in result.stdout
    assert "Sentinel.UNSET" not in result.stdout
    for parameter in command.params:
        if isinstance(parameter, click.Option) and not parameter.hidden:
            assert parameter.opts[0] in result.stdout
    optional = [
        p for p in command.params if isinstance(p, click.Option) and not p.hidden and not p.required
    ]
    assert result.stdout.count("Default:") >= len(optional)
    from monarch_cli.core.help_reference import examples_for

    examples = examples_for(command, "monarch" + (" " + " ".join(words) if words else ""))
    assert 2 <= len(examples) <= 3
    for example in examples:
        assert example == "monarch" or example.startswith("monarch " + " ".join(words))
        assert "\n" not in example
        assert re.search(r"--help(?:\s|$)", example) is None
        # Parsing invokes no callbacks/dependencies. Placeholder files are checked below.
        args = shlex.split(example)[1:]
        for name in [
            "password.txt",
            "history.csv",
            "receipt.pdf",
            "splits.json",
            "filters.json",
            "view.json",
        ]:
            if name in args:
                target = tmp_path / name
                target.write_text("{}")
                args = [str(target) if value == name else value for value in args]
        root = get_command(app)
        ctx = root.make_context("monarch", args)
        with ctx:
            current = root
            while isinstance(current, click.Group):
                remaining = ctx._protected_args + ctx.args
                if not remaining:
                    break
                _, child, rest = current.resolve_command(ctx, remaining)
                assert child is not None
                ctx = child.make_context(child.name, rest, parent=ctx)
                current = child
            for parameter in current.params:
                if parameter.required:
                    assert ctx.params.get(parameter.name) is not None, example
