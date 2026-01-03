import os
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timedelta
from homelab_backup_manager.config import Config, BackupJob, GlobalConfig
from homelab_backup_manager.backup import DockerComposeStrategy, BackupManager

@pytest.fixture
def mock_config():
    return Config(
        global_settings=GlobalConfig(
            backup_root="/tmp/backups",
            retention_days=7,
            telegram=None
        ),
        jobs=[
            BackupJob(
                name="test_service",
                strategy="docker-compose",
                service_path="/tmp/service"
            )
        ]
    )

def test_docker_compose_strategy(mock_config, mocker):
    # Mock os.makedirs
    mocker.patch("os.makedirs")
    # Mock subprocess
    mock_subprocess = mocker.patch("subprocess.run")
    # Mock os.path.exists
    mocker.patch("os.path.exists", return_value=True)
    
    job = mock_config.jobs[0]
    strategy = DockerComposeStrategy(job, mock_config.global_settings)
    
    # Mock os.path.join to behave predictably if needed, but standard behavior is fine
    
    path = strategy.run()
    
    # Verify calls
    assert mock_subprocess.call_count == 3
    # 1. Down
    assert mock_subprocess.call_args_list[0] == call(["docker", "compose", "down"], cwd="/tmp/service", check=True)
    # 2. Tar
    # We can't easily match the exact file name due to timestamp, but we can check the command structure
    args, kwargs = mock_subprocess.call_args_list[1]
    assert args[0][0] == "tar"
    assert args[0][1] == "-czf"
    assert args[0][3] == "."
    assert kwargs['cwd'] == "/tmp/service"
    
    # 3. Up
    assert mock_subprocess.call_args_list[2] == call(["docker", "compose", "up", "-d"], cwd="/tmp/service", check=True)

def test_cleanup_logic(mock_config, mocker):
    mocker.patch("os.makedirs")
    mocker.patch("os.listdir", return_value=["old_backup.tar.gz", "new_backup.tar.gz"])
    mocker.patch("os.path.isfile", return_value=True)
    mock_remove = mocker.patch("os.remove")
    
    # Mock getmtime
    now = datetime.now().timestamp()
    old_time = (datetime.now() - timedelta(days=10)).timestamp()
    
    def getmtime_side_effect(path):
        if "old_backup" in path:
            return old_time
        return now
        
    mocker.patch("os.path.getmtime", side_effect=getmtime_side_effect)
    
    job = mock_config.jobs[0]
    strategy = DockerComposeStrategy(job, mock_config.global_settings)
    strategy.cleanup()
    
    # Should delete the old one
    mock_remove.assert_called_once()
    assert "old_backup.tar.gz" in mock_remove.call_args[0][0]

def test_postgres_strategy(mocker):
    # Setup config
    job = BackupJob(name="db", strategy="postgres-dump", container_name="db_container", db_user="pguser")
    global_config = GlobalConfig(backup_root="/tmp/backups")
    
    # Mock docker client
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_client.containers.get.return_value = mock_container
    mocker.patch("docker.from_env", return_value=mock_client)
    
    # Mock subprocess
    mock_subprocess = mocker.patch("subprocess.run")
    mocker.patch("os.makedirs")
    
    from homelab_backup_manager.backup import PostgresDumpStrategy
    strategy = PostgresDumpStrategy(job, global_config)
    strategy.run()
    
    # Verify docker client got container
    mock_client.containers.get.assert_called_with("db_container")
    
    # Verify subprocess call
    args, _ = mock_subprocess.call_args
    assert "docker exec -i db_container pg_dumpall" in args[0]
    assert "| gzip >" in args[0]

def test_command_strategy(mocker):
    job = BackupJob(name="pihole", strategy="command", dump_command="pihole-FTL --teleporter")
    global_config = GlobalConfig(backup_root="/tmp/backups")
    
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_client.containers.get.return_value = mock_container
    mocker.patch("docker.from_env", return_value=mock_client)
    
    # Mock container find results
    mock_container.exec_run.side_effect = [
        (0, b"Success"), # dump_command
        (0, b"/pi-hole-teleporter.zip\n") # find_cmd
        , (0, b"Removed") # rm
    ]
    mock_container.get_archive.return_value = (MagicMock(), MagicMock())
    # Mock subprocess for docker cp
    mock_subprocess = mocker.patch("subprocess.run")
    mocker.patch("os.makedirs")
    
    from homelab_backup_manager.backup import CommandStrategy
    strategy = CommandStrategy(job, global_config)
    strategy.run()
    
    assert mock_container.exec_run.call_count == 3
    mock_subprocess.assert_called()

def test_command_strategy_no_file(mocker):
    job = BackupJob(name="pihole", strategy="command", dump_command="cmd")
    global_config = GlobalConfig(backup_root="/tmp/backups")
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_client.containers.get.return_value = mock_container
    mocker.patch("docker.from_env", return_value=mock_client)
    mock_container.exec_run.return_value = (0, b"") # Empty find
    mocker.patch("os.makedirs")
    
    from homelab_backup_manager.backup import CommandStrategy
    strategy = CommandStrategy(job, global_config)
    with pytest.raises(RuntimeError, match="No backup file generated"):
        strategy.run()

def test_docker_compose_strategy_path_not_found(mocker):
    job = BackupJob(name="test", strategy="docker-compose", service_path="/invalid")
    mocker.patch("os.path.exists", return_value=False)
    mocker.patch("os.makedirs")
    from homelab_backup_manager.backup import DockerComposeStrategy
    strategy = DockerComposeStrategy(job, GlobalConfig())
    with pytest.raises(FileNotFoundError):
        strategy.run()

def test_backup_manager_run_all_with_failure(mock_config, mocker):
    manager = BackupManager.__new__(BackupManager)
    manager.config = mock_config
    manager.notifier = MagicMock()
    
    mocker.patch("homelab_backup_manager.backup.DockerComposeStrategy.run", side_effect=Exception("Failed"))
    mocker.patch("homelab_backup_manager.backup.DockerComposeStrategy.cleanup")
    
    manager.run_all()
    assert manager.notifier.send.called

def test_backup_manager_run_job_success(mock_config, mocker):
    from homelab_backup_manager.backup import BackupManager
    manager = BackupManager.__new__(BackupManager)
    manager.config = mock_config
    
    mock_strategy = MagicMock()
    mocker.patch("homelab_backup_manager.backup.DockerComposeStrategy", return_value=mock_strategy)
    
    manager.run_job("test_service")
    mock_strategy.run.assert_called_once()

def test_notifier_success(mocker):
    from homelab_backup_manager.notifier import TelegramNotifier, TelegramConfig
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.raise_for_status = MagicMock()
    
    config = TelegramConfig(token="test_token", chat_id="123")
    notifier = TelegramNotifier(config)
    notifier.send("test message")
    
    mock_post.assert_called_once()
    assert "test_token" in mock_post.call_args[0][0]

def test_notifier_failure(mocker):
    from homelab_backup_manager.notifier import TelegramNotifier, TelegramConfig
    import requests
    mock_post = mocker.patch("requests.post", side_effect=requests.RequestException("Error"))
    mocker.patch("time.sleep") # speed up tests
    
    config = TelegramConfig(token="test_token", chat_id="123")
    notifier = TelegramNotifier(config)
    notifier.send("test message")
    
    assert mock_post.call_count == 3

def test_backup_manager_run_all(mock_config, mocker):
    mocker.patch("builtins.open", mocker.mock_open(read_data='global_settings: {}\njobs: []'))
    # Mock Config class instead of file loading for simplicity in this test
    from homelab_backup_manager.backup import BackupManager
    
    # Actually we want to test the orchestration
    manager = BackupManager.__new__(BackupManager)
    manager.config = mock_config
    manager.notifier = MagicMock()
    
    # Mock the strategy and its run
    mock_strategy = MagicMock()
    mock_strategy.run.return_value = "/tmp/backups/test_service/backup.tar.gz"
    mocker.patch("os.path.getsize", return_value=1024*1024)
    mocker.patch("homelab_backup_manager.backup.DockerComposeStrategy", return_value=mock_strategy)
    
    manager.run_all()
    
    mock_strategy.run.assert_called_once()
    mock_strategy.cleanup.assert_called_once()
    manager.notifier.send.assert_called_once()

def test_backup_manager_run_job_not_found(mock_config, mocker):
    from homelab_backup_manager.backup import BackupManager
    manager = BackupManager.__new__(BackupManager)
    manager.config = mock_config
    
    # Should just log error and return
    manager.run_job("non_existent")

def test_backup_manager_init(mocker):
    from homelab_backup_manager.backup import BackupManager
    mocker.patch("builtins.open", mocker.mock_open(read_data='global_settings: {backup_root: /tmp}\njobs: []'))
    manager = BackupManager("config.yaml")
    assert manager.config.global_settings.backup_root == "/tmp"

def test_unknown_strategy(mock_config):
    from homelab_backup_manager.backup import BackupManager
    manager = BackupManager.__new__(BackupManager)
    mock_config.jobs[0].strategy = "invalid"
    
    with pytest.raises(ValueError, match="Unknown strategy"):
        manager._get_strategy(mock_config.jobs[0])

