"""
Command Line Interface for the Homelab Backup Manager.
"""
import logging
import os
import click
from .backup import BackupManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

@click.group()
@click.option('--config', default='config.yaml', help='Path to configuration file')
@click.pass_context
def cli(ctx, config):
    """Homelab Backup Manager CLI."""
    if not os.path.exists(config):
        # Fallback to absolute path if not found in cwd
        # Or look in standard locations
        pass
    ctx.ensure_object(dict)
    ctx.obj['CONFIG_PATH'] = config

@cli.command()
@click.pass_context
def run_all(ctx):
    """Runs all enabled backup jobs."""
    manager = BackupManager(ctx.obj['CONFIG_PATH'])
    manager.run_all()

@cli.command()
@click.argument('job_name')
@click.pass_context
def run(ctx, job_name):
    """Runs a single backup job."""
    manager = BackupManager(ctx.obj['CONFIG_PATH'])
    manager.run_job(job_name)

if __name__ == '__main__':
    cli(obj={}) # pylint: disable=no-value-for-parameter,unexpected-keyword-arg
