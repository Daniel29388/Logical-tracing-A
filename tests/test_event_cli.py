from typer.testing import CliRunner

from cli.main import app


def test_event_command_is_registered():
    runner = CliRunner()

    result = runner.invoke(app, ["event", "--help"])

    assert result.exit_code == 0
    assert "--seed" in result.output
    assert "--quick-model" in result.output
