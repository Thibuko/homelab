import click
from click.testing import CliRunner
from unittest.mock import MagicMock, patch
from homelab_backup_manager.cli import cli

def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'Show this message and exit.' in result.output

@patch('homelab_backup_manager.cli.BackupManager')
def test_cli_run_all(mock_manager_class):
    mock_manager = MagicMock()
    mock_manager_class.return_value = mock_manager
    
    runner = CliRunner()
    result = runner.invoke(cli, ['run-all'])
    
    assert result.exit_code == 0
    mock_manager.run_all.assert_called_once()

@patch('homelab_backup_manager.cli.BackupManager')
def test_cli_run_job(mock_manager_class):
    mock_manager = MagicMock()
    mock_manager_class.return_value = mock_manager
    
    runner = CliRunner()
    result = runner.invoke(cli, ['run', 'test_job'])
    
    assert result.exit_code == 0
    mock_manager.run_job.assert_called_with('test_job')

def test_main_invocation():
    # Test main.py indirectly or just ensure cli is callable
    from homelab_backup_manager.main import cli as main_cli
    assert main_cli.name == 'cli'
