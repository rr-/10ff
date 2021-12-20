"""Terminal manipulation utilities."""
import asyncio
import contextlib
import os
import sys
import termios
import tty
import typing as T
from enum import IntEnum


class TextColor(IntEnum):
    """Text color."""

    RED = 1
    GREEN = 2
    YELLOW = 3
    DEFAULT = 4


def move_cursor_up(num: int) -> None:
    """Move the caret up by the specified number of lines.

    :param num: how many lines to go.
    """
    sys.stdout.write("\x1B[{}F".format(num))


def set_text_color(color: TextColor) -> None:
    """Change the color of the text to the given value.

    :param color: color to set"""
    sys.stdout.write(
        {
            TextColor.RED: "\x1B[31;1m",
            TextColor.GREEN: "\x1B[32;1m",
            TextColor.YELLOW: "\x1B[33;1m",
            TextColor.DEFAULT: "\x1B[0m",
        }[color]
    )


def erase_whole_line() -> None:
    """Erase the entire line where the caret is at."""
    sys.stdout.write("\x1B[999D\x1B[K")


class TerminalInputHandler:
    """A class for terminal manipulation."""

    def __init__(self, loop: asyncio.events.AbstractEventLoop) -> None:
        """Initialize self.

        :param loop: the event loop.
        """
        self.fd = sys.stdin.fileno()
        self.loop = loop
        self.old_settings: T.Optional[T.List[T.Any]] = None

        self.input_queue: asyncio.Queue[str] = asyncio.Queue()
        loop.add_reader(sys.stdin, self.got_input)

    @contextlib.contextmanager
    def enable_raw_terminal(self) -> T.Iterator[None]:
        """A context manager that enables unbuffered input."""
        self.old_settings = termios.tcgetattr(self.fd)
        tty.setraw(self.fd)

        new_settings = termios.tcgetattr(self.fd)
        new_settings[3] = new_settings[3] & ~(
            termios.ECHO | termios.ICANON
        )  # lflags
        new_settings[6][termios.VMIN] = 0  # cc
        new_settings[6][termios.VTIME] = 0  # cc
        termios.tcsetattr(self.fd, termios.TCSADRAIN, new_settings)

        try:
            yield
        finally:
            if self.old_settings is not None:
                termios.tcsetattr(
                    self.fd, termios.TCSADRAIN, self.old_settings
                )

    def got_input(self) -> None:
        """Handle the keypress event."""
        keys_raw = b""
        key = os.read(self.fd, 1)
        while key is not None and len(key) > 0:
            keys_raw += key
            key = os.read(self.fd, 1)
        keys_str = keys_raw.decode()

        asyncio.ensure_future(self.input_queue.put(keys_str), loop=self.loop)
