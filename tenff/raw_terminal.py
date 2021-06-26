"""Terminal manipulation utilities."""
import asyncio
import os
import sys
import termios
import tty
import typing as T


class RawTerminal:
    """A class for terminal manipulation."""

    def __init__(self, loop: asyncio.events.AbstractEventLoop) -> None:
        """Initialize self.

        :param loop: the event loop.
        """
        self._fd = sys.stdin.fileno()
        self._loop = loop
        self._old_settings: T.Optional[T.List[T.Any]] = None
        self.input_queue: asyncio.Queue[T.Optional[str]] = asyncio.Queue(
            loop=loop
        )
        loop.add_reader(sys.stdin, self._got_input)

    @staticmethod
    def move_cursor_up(num: int) -> None:
        """Move the caret up by the specified number of lines.

        :param num: how many lines to go.
        """
        sys.stdout.write("\x1B[{}F".format(num))

    @staticmethod
    def set_red_font() -> None:
        """Change the color of the text to red."""
        sys.stdout.write("\x1B[31;1m")

    @staticmethod
    def set_green_font() -> None:
        """Change the color of the text to green."""
        sys.stdout.write("\x1B[32;1m")

    @staticmethod
    def set_yellow_font() -> None:
        """Change the color of the text to yellow."""
        sys.stdout.write("\x1B[33;1m")

    @staticmethod
    def set_default_font() -> None:
        """Reset the color of the text."""
        sys.stdout.write("\x1B[39m")

    @staticmethod
    def erase_whole_line() -> None:
        """Erase the entire line where the caret is at."""
        sys.stdout.write("\x1B[999D\x1B[K")

    def enable(self) -> None:
        """Enable unbuffered input."""
        self._old_settings = termios.tcgetattr(self._fd)
        tty.setraw(self._fd)

        new_settings = termios.tcgetattr(self._fd)
        new_settings[3] = new_settings[3] & ~(
            termios.ECHO | termios.ICANON
        )  # lflags
        new_settings[6][termios.VMIN] = 0  # cc
        new_settings[6][termios.VTIME] = 0  # cc
        termios.tcsetattr(self._fd, termios.TCSADRAIN, new_settings)

    def disable(self) -> None:
        """Disable unbuffered input."""
        if self._old_settings is not None:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)

    def _got_input(self) -> None:
        """Handle the keypress event."""
        keys_raw = b""
        key = os.read(self._fd, 1)
        while key is not None and len(key) > 0:
            keys_raw += key
            key = os.read(self._fd, 1)
        keys_str = keys_raw.decode()

        asyncio.ensure_future(self.input_queue.put(keys_str), loop=self._loop)
