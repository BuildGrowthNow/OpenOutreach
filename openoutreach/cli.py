# openoutreach/cli.py
"""
Click CLI for OpenOutreach - replaces Django's manage.py.
Pure Python command-line interface with no Django dependencies.
"""
import click
import logging
import sys


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging (DEBUG level)')
def cli(verbose):
    """OpenOutreach CLI - LinkedIn Automation Platform."""
    # Configure logging
    from openoutreach.core.logging import configure_logging
    level = logging.DEBUG if verbose else logging.INFO
    configure_logging(level=level)


@cli.command()
@click.option('--host', default='0.0.0.0', help='API host')
@click.option('--port', default=8001, type=int, help='API port')
@click.option('--reload', is_flag=True, help='Auto-reload on code changes')
@click.option('--workers', default=1, type=int, help='Number of worker processes')
def runserver(host, port, reload, workers):
    """Run the FastAPI server."""
    import uvicorn
    from openoutreach.api_v2.main import app
    from openoutreach.mongodb.connection import initialize_mongodb_connection
    from openoutreach.mongodb.indexes import ensure_all_indexes

    # Initialize MongoDB on startup
    initialize_mongodb_connection()
    ensure_all_indexes()

    click.echo(f"Starting FastAPI server at http://{host}:{port}")
    click.echo(f"API docs available at http://{host}:{port}/docs")

    uvicorn.run(
        "openoutreach.api_v2.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        log_level="info"
    )


@cli.command()
def rundaemon():
    """Run the OpenOutreach daemon (task queue worker).

    The daemon handles LinkedIn automation tasks:
    - Discovering and qualifying leads
    - Sending connection requests
    - Following up with personalized messages
    - Monitoring campaign health

    Manages all active LinkedIn profiles automatically (multi-tenant).
    """
    from openoutreach.core.logging import print_banner

    print_banner()
    click.echo("Starting multi-profile daemon...")

    from openoutreach.core.daemon import run_daemon
    run_daemon()




@cli.command()
def ensure_indexes():
    """Create all MongoDB indexes.

    This command ensures all required indexes are created in MongoDB.
    It's safe to run multiple times (idempotent).
    """
    from openoutreach.mongodb.connection import initialize_mongodb_connection
    from openoutreach.mongodb.indexes import ensure_all_indexes

    click.echo("Initializing MongoDB connection...")
    initialize_mongodb_connection()

    click.echo("Creating indexes...")
    ensure_all_indexes()

    click.echo("All indexes created successfully!")


@cli.command()
def shell():
    """Open an interactive Python shell with OpenOutreach context.

    Provides access to:
    - MongoDB models
    - Data Access Layer (DAL)
    - Configuration
    """
    import code
    from openoutreach.mongodb import models
    from openoutreach.mongodb import dal
    from openoutreach.config import settings
    from openoutreach.mongodb.connection import initialize_mongodb_connection

    initialize_mongodb_connection()

    banner = """
OpenOutreach Interactive Shell
==============================
Available imports:
  - models   (MongoDB models)
  - dal      (Data Access Layer)
  - settings (Application settings)

Example usage:
  >>> user = models.User.get_by_email("user@example.com")
  >>> campaigns = dal.CampaignDAL.get_user_campaigns(user._id)
  >>> task = dal.TaskDAL.claim_next_task()
"""

    code.interact(
        banner=banner,
        local={
            'models': models,
            'dal': dal,
            'settings': settings,
        }
    )


@cli.command()
@click.option('--format', type=click.Choice(['json', 'yaml', 'env']), default='env', help='Output format')
def showconfig(format):
    """Show current configuration (environment variables).

    Displays all configuration values without exposing secrets.
    """
    from openoutreach.config import settings

    if format == 'json':
        import json
        config = _get_safe_config(settings)
        click.echo(json.dumps(config, indent=2))
    elif format == 'yaml':
        import yaml
        config = _get_safe_config(settings)
        click.echo(yaml.dump(config, default_flow_style=False))
    else:  # env
        config = _get_safe_config(settings)
        for key, value in config.items():
            click.echo(f"{key}={value}")


@cli.command()
def healthcheck():
    """Check system health (MongoDB connection, API availability).

    Returns exit code 0 if healthy, non-zero if unhealthy.
    """
    from openoutreach.mongodb.connection import initialize_mongodb_connection, mongodb_connection

    try:
        # Check MongoDB connection
        click.echo("Checking MongoDB connection...")
        initialize_mongodb_connection()
        if mongodb_connection.client is None:
            click.echo("❌ MongoDB connection failed", err=True)
            sys.exit(1)

        # Try to ping MongoDB
        mongodb_connection.client.admin.command('ping')
        click.echo("✅ MongoDB connection OK")

        # Check if API server is running (optional)
        import httpx
        from openoutreach.config import settings
        try:
            response = httpx.get(f"http://{settings.API_HOST}:{settings.API_PORT}/api/health", timeout=5.0)
            if response.status_code == 200:
                click.echo("✅ API server OK")
            else:
                click.echo(f"⚠️  API server returned {response.status_code}")
        except httpx.ConnectError:
            click.echo("⚠️  API server not running (this is OK if only running daemon)")

        click.echo("\n✅ System health check passed")
        sys.exit(0)

    except Exception as e:
        click.echo(f"❌ Health check failed: {e}", err=True)
        sys.exit(1)


# ============================================================================
# Helper Functions
# ============================================================================




def _get_safe_config(settings):
    """Get configuration dict with secrets masked."""
    config = {}
    sensitive_keys = {
        'SECRET_KEY', 'JWT_SECRET_KEY', 'COOKIE_ENCRYPTION_KEY',
        'LLM_API_KEY', 'LINKEDIN_PASSWORD', 'SUPABASE_SERVICE_KEY',
        'FINDER_API_KEY'
    }

    for key in dir(settings):
        if key.startswith('_') or key.upper() != key:
            continue
        value = getattr(settings, key)
        if callable(value):
            continue
        if key in sensitive_keys and value:
            config[key] = "***HIDDEN***"
        else:
            config[key] = str(value) if value is not None else ""

    return config


if __name__ == '__main__':
    cli()
