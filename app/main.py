"""FastAPI application entry point."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Create the FastAPI application.

    Configuration, middleware, routers, and exception handlers are added in
    their dedicated implementation stages.
    """
    return FastAPI(
        title="AI Contact API",
        description="API for portfolio contact requests with AI classification.",
        version="0.1.0",
    )


app = create_app()
