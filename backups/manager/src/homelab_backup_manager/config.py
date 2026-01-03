"""
Configuration models for the backup manager.
"""
from typing import List, Optional
from pydantic import BaseModel, Field

class TelegramConfig(BaseModel):
    """Configuration for Telegram notifications."""
    token: str
    chat_id: str
    enabled: bool = True

class GlobalConfig(BaseModel):
    """Global settings for the application."""
    backup_root: str = "/data/backups"
    retention_days: int = 7
    telegram: Optional[TelegramConfig] = None
    docker_root: str = "/docker"

class BackupJob(BaseModel):
    """Configuration for a single backup job."""
    name: str
    enabled: bool = True
    strategy: str  # 'docker-compose', 'postgres-dump', 'command'
    container_name: Optional[str] = None
    service_path: Optional[str] = None # Path to folder containing docker-compose.yml
    source_paths: List[str] = [] # For file-based backups
    exclude_patterns: List[str] = []

    # Strategy specific
    db_user: str = "postgres"
    db_name: Optional[str] = None
    dump_command: Optional[str] = None # For custom command strategy
    file_extension: str = ".tar.gz"

class Config(BaseModel):
    """Root configuration object."""
    global_settings: GlobalConfig = Field(default_factory=GlobalConfig)
    jobs: List[BackupJob] = []
