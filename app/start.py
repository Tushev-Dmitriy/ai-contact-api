"""Production container entry point."""

import os
import subprocess

from app.core.config import get_settings


def main() -> None:
    """Apply database migrations and replace this process with Uvicorn."""
    settings = get_settings()
    subprocess.run(
        ["alembic", "upgrade", "head"],
        check=True,
    )
    os.execvp(
        "uvicorn",
        [
            "uvicorn",
            "app.main:app",
            "--host",
            settings.app_host,
            "--port",
            str(settings.app_port),
        ],
    )


if __name__ == "__main__":
    main()
