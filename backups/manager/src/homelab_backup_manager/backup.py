"Core backup logic and strategies."
import os
import logging
import subprocess
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List
import yaml
import docker
from docker.errors import NotFound

from .config import Config, BackupJob, GlobalConfig
from .notifier import TelegramNotifier

logger = logging.getLogger(__name__)

class BackupStrategy(ABC):
    """Abstract base class for backup strategies."""
    def __init__(self, job: BackupJob, global_config: GlobalConfig):
        self.job = job
        self.global_config = global_config
        self.client = docker.from_env()
        self.backup_dir = os.path.join(global_config.backup_root, job.name)
        os.makedirs(self.backup_dir, exist_ok=True)

    @abstractmethod
    def run(self) -> str:
        """Executes the backup and returns the path to the backup file."""

    def cleanup(self):
        """Deletes backups older than retention_days."""
        retention = self.global_config.retention_days
        if retention <= 0:
            return

        cutoff = datetime.now() - timedelta(days=retention)
        logger.info("Cleaning up backups for %s older than %d days.", self.job.name, retention)

        for filename in os.listdir(self.backup_dir):
            file_path = os.path.join(self.backup_dir, filename)
            if os.path.isfile(file_path):
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                if file_mtime < cutoff:
                    logger.info("Deleting old backup: %s", filename)
                    os.remove(file_path)

class DockerComposeStrategy(BackupStrategy):
    """
    Stops the docker compose stack, creates a tar archive of the directory,
    and restarts the stack.
    """
    def run(self) -> str:
        service_path = self.job.service_path
        if not service_path:
            # Try to guess based on standard convention
            service_path = os.path.join(self.global_config.docker_root, self.job.name)

        if not os.path.exists(service_path):
            raise FileNotFoundError(f"Service path not found: {service_path}")

        timestamp = datetime.now().strftime("%Y-%m-%d")
        filename = f"{self.job.name}_backup_{timestamp}.tar.gz"
        dest_path = os.path.join(self.backup_dir, filename)

        logger.info("Stopping services in %s...", service_path)
        subprocess.run(["docker", "compose", "down"], cwd=service_path, check=True)

        try:
            logger.info("Creating archive %s...", dest_path)
            # Using tar command for performance and permission preservation
            cmd = ["tar", "-czf", dest_path]
            for exclude in self.job.exclude_patterns:
                cmd.append(f"--exclude={exclude}")
            cmd.append(".")

            subprocess.run(cmd, cwd=service_path, check=True)
            logger.info("Archive created successfully.")

        finally:
            logger.info("Restarting services in %s...", service_path)
            subprocess.run(["docker", "compose", "up", "-d"], cwd=service_path, check=True)

        return dest_path

class PostgresDumpStrategy(BackupStrategy):
    """
    Performs a live pg_dumpall on a running container.
    """
    def run(self) -> str:
        container_name = self.job.container_name or f"{self.job.name}_postgres"
        try:
            # Check if container exists (unused variable 'container' fixed by not assigning)
            self.client.containers.get(container_name)
        except NotFound as exc:
            raise RuntimeError(f"Container {container_name} not found.") from exc

        timestamp = datetime.now().strftime("%Y-%m-%d")
        hostname = os.uname().nodename
        filename = f"{hostname}_{self.job.name}_db_{timestamp}.sql.gz"
        dest_path = os.path.join(self.backup_dir, filename)

        logger.info("Dumping PostgreSQL database from %s...", container_name)

        cmd = (
            f"docker exec -i {container_name} pg_dumpall -c -U {self.job.db_user} "
            f"| gzip > {dest_path}"
        )
        subprocess.run(cmd, shell=True, check=True)

        return dest_path

class CommandStrategy(BackupStrategy):
    """
    Runs a custom command inside the container (e.g., pihole teleporter)
    and copies the resulting file out.
    """
    def run(self) -> str:
        container_name = self.job.container_name or self.job.name
        try:
            container = self.client.containers.get(container_name)
        except NotFound as exc:
            raise RuntimeError(f"Container {container_name} not found.") from exc

        logger.info("Running command: %s", self.job.dump_command)

        if not self.job.dump_command:
            raise ValueError(f"dump_command is required for strategy 'command' in job {self.job.name}")

        exit_code, output = container.exec_run(self.job.dump_command)
        if exit_code != 0:
            raise RuntimeError(f"Command failed: {output.decode()}")

        find_cmd = 'find / -maxdepth 1 -name "pi-hole*teleporter*.zip" -print'
        exit_code, output = container.exec_run(find_cmd)
        files = output.decode().strip().split('\n')
        files = [f for f in files if f]

        if not files:
            raise RuntimeError("No backup file generated/found inside container.")

        src_path = files[0]
        basename = os.path.basename(src_path)
        dest_path = os.path.join(self.backup_dir, basename)

        logger.info("Copying %s from container to %s...", src_path, dest_path)

        subprocess.run(
            ["docker", "cp", f"{container_name}:{src_path}", dest_path],
            check=True
        )

        container.exec_run(f"rm {src_path}")

        return dest_path


class BackupManager:
    """Orchestrates the backup process for all configured jobs."""
    def __init__(self, config_path: str):
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        self.config = Config(**data)
        # pylint: disable=no-member
        self.notifier = TelegramNotifier(self.config.global_settings.telegram)

    def run_all(self):
        """Runs all enabled backup jobs and sends a report."""
        report = []
        success_count = 0
        fail_count = 0

        for job in self.config.jobs:
            if not job.enabled:
                continue

            try:
                logger.info("Starting backup for %s...", job.name)
                strategy = self._get_strategy(job)
                filepath = strategy.run()
                strategy.cleanup()

                size = os.path.getsize(filepath) / (1024 * 1024) # MB
                report.append(f"✅ *{job.name}*: {size:.2f} MB")
                success_count += 1
                logger.info("Backup %s success.", job.name)

            except Exception as e: # pylint: disable=broad-exception-caught
                logger.error("Backup %s failed: %s", job.name, e, exc_info=True)
                report.append(f"❌ *{job.name}*: Failed ({str(e)})")
                fail_count += 1

        self._send_report(report, success_count, fail_count)

    def run_job(self, job_name: str):
        """Runs a single backup job by name."""
        job = next((j for j in self.config.jobs if j.name == job_name), None)
        if not job:
            logger.error("Job %s not found.", job_name)
            return

        try:
            strategy = self._get_strategy(job)
            filepath = strategy.run()
            strategy.cleanup()
            print(f"Backup successful: {filepath}")
        except Exception as e:
            logger.error("Backup failed: %s", e, exc_info=True)
            raise e

    def _get_strategy(self, job: BackupJob) -> BackupStrategy:
        if job.strategy == "docker-compose":
            return DockerComposeStrategy(job, self.config.global_settings)
        if job.strategy == "postgres-dump":
            return PostgresDumpStrategy(job, self.config.global_settings)
        if job.strategy == "command":
            return CommandStrategy(job, self.config.global_settings)

        raise ValueError(f"Unknown strategy: {job.strategy}")

    def _send_report(self, report_lines: List[str], success: int, fail: int):
        hostname = os.uname().nodename
        date_str = datetime.now().strftime("%Y-%m-%d")

        header = f"📊 *Backup Report - {hostname} ({date_str})*\n"
        summary = f"Total: {success + fail} | Success: {success} | Failed: {fail}\n\n"

        msg = header + summary + "\n".join(report_lines)
        self.notifier.send(msg)
