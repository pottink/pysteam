"""Compact, redacted terminal logging for the opt-in CLI debug mode."""

from __future__ import annotations

import logging
from datetime import datetime

from rich.console import Console
from rich.text import Text


class CompactRichHandler(logging.Handler):
    def __init__(self, console: Console) -> None:
        super().__init__()
        self.console = console

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = Text()
            timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")
            line.append(timestamp[:-3], style="dim")
            line.append(" | ", style="dim")
            level_style = (
                "red"
                if record.levelno >= logging.ERROR
                else "yellow"
                if record.levelno >= logging.WARNING
                else "cyan"
            )
            line.append(f"{record.levelname:<5}", style=level_style)
            line.append(" | ", style="dim")
            line.append(self.format(record))
            self.console.print(line)
        except Exception:
            self.handleError(record)


def enable_debug_logging(console: Console) -> logging.Handler:
    logger = logging.getLogger("pysteam")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    handler = CompactRichHandler(console)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return handler
