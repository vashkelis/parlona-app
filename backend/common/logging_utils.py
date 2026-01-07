import logging
import sys

from backend.common.config import get_settings


class _ServiceContextFilter(logging.Filter):
    """Ensures every log record carries the service name."""

    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401 (simple)
        record.service = self.service_name
        return True


def configure_logging(service_name: str | None = None) -> None:
    """Configure root logger with consistent formatter and context."""

    settings = get_settings()
    log_service_name = service_name or settings.service_name

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] (%(service)s) %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    handler.addFilter(_ServiceContextFilter(log_service_name))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers in reconfig scenarios
    root_logger.handlers = []
    root_logger.addHandler(handler)


class ServiceLogger(logging.LoggerAdapter):
    """Convenience adapter embedding service name."""

    def __init__(self, name: str) -> None:
        settings = get_settings()
        super().__init__(logging.getLogger(name), {"service": settings.service_name})
