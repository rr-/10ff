import asyncio
import os
import sys
import termios
import tty


class RawTerminal:
    def __init__(self, loop):
        self._fd = sys.stdin.fileno()
        self._loop = loop
        self._old_settings = None
        self.input_queue = asyncio.Queue(loop=loop)
        loop.add_reader(sys.stdin, self._got_input)

    @staticmethod
    def move_cursor_up(num):
        sys.stdout.write("\x1B[{}F".format(num))

    @staticmethod
    def set_red_font():
        sys.stdout.write("\x1B[31;1m")

    @staticmethod
    def set_green_font():
        sys.stdout.write("\x1B[32;1m")

    @staticmethod
    def set_yellow_font():
        sys.stdout.write("\x1B[33;1m")

    @staticmethod
    def set_default_font():
        sys.stdout.write("\x1B[39m")

    @staticmethod
    def erase_whole_line():
        sys.stdout.write("\x1B[999D\x1B[K")

    def enable(self):
        self._old_settings = termios.tcgetattr(self._fd)
        tty.setraw(self._fd)

        new_settings = termios.tcgetattr(self._fd)
        new_settings[3] = new_settings[3] & ~(
            termios.ECHO | termios.ICANON
        )  # lflags
        new_settings[6][termios.VMIN] = 0  # cc
        new_settings[6][termios.VTIME] = 0  # cc
        termios.tcsetattr(self._fd, termios.TCSADRAIN, new_settings)

    def disable(self):
        termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)

    def _got_input(self, *args, **kwargs):
        keys = b""
        ch = os.read(self._fd, 1)
        while ch != None and len(ch) > 0:
            keys += ch
            ch = os.read(self._fd, 1)
        keys = keys.decode()

        asyncio.ensure_future(self.input_queue.put(keys), loop=self._loop)
