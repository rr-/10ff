#!/usr/bin/env python3
import asyncio
import argparse
import pathlib
import re
import time
import random
import sys
import shutil
import tty
import termios

MAX_TIME = 60
MAX_COLUMNS = min(shutil.get_terminal_size().columns, 80)
MAX_LINES = 2
WORD_LENGTH = 5
SAMPLE_SIZE = 1000

STATUS_UNTYPED = 0
STATUS_TYPING = 1
STATUS_TYPED_WELL = 2
STATUS_TYPED_WRONG = 3


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c', '--corpus', type=pathlib.Path, dest='corpus_path',
        default=pathlib.Path(__file__).parent / 'data' / 'english.txt')
    parser.add_argument('-w', '--width', type=int, default=80)
    return parser.parse_args()


def divide_lines(words):
    lines = []
    current_line = ''
    words_left = words[:]
    while len(words_left):
        current_line = ''
        low = len(words) - len(words_left)
        while len(words_left):
            word = words_left[0]
            new_line = (current_line + ' ' + word).strip()
            if len(new_line) >= MAX_COLUMNS:
                break
            words_left = words_left[1:]
            current_line = new_line
        high = len(words) - len(words_left)
        lines.append((low, high))
    return lines


class RawTerminal:
    def __init__(self, loop):
        self._fd = sys.stdin.fileno()
        self._loop = loop
        self._old_settings = None
        self.input_queue = asyncio.Queue(loop=loop)
        loop.add_reader(sys.stdin, self._got_input)

    @staticmethod
    def move_cursor_up(num):
        sys.stdout.write(f'\x1B[{num}F')

    @staticmethod
    def set_red_font():
        sys.stdout.write('\x1B[31;1m')

    @staticmethod
    def set_green_font():
        sys.stdout.write('\x1B[32;1m')

    @staticmethod
    def set_yellow_font():
        sys.stdout.write('\x1B[33;1m')

    @staticmethod
    def set_default_font():
        sys.stdout.write('\x1B[39m')

    @staticmethod
    def erase_whole_line():
        sys.stdout.write('\x1B[999D\x1B[K')

    def enable(self):
        self._old_settings = termios.tcgetattr(self._fd)
        tty.setraw(self._fd)

    def disable(self):
        termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)

    def _got_input(self):
        asyncio.ensure_future(
            self.input_queue.put(sys.stdin.read(1)), loop=self._loop)


class GameState:
    def __init__(self, words):
        self._words = words
        self._current_word = 0
        self._text_input = ''
        self._status = [STATUS_TYPING] + [STATUS_UNTYPED for _ in words[1:]]
        self._line_boundaries = divide_lines(words)
        self._time_left = MAX_TIME
        self._start_time = time.time()
        self._end_time = None
        self._total_keys_pressed = 0
        self._current_word_keys_pressed = 0
        self._first_render = True

    @property
    def finished(self):
        return self._end_time is not None

    @property
    def _current_line(self):
        for i, (low, high) in enumerate(self._line_boundaries):
            if self._current_word in range(low, high):
                return i
        return len(self._line_boundaries) - 1

    @property
    def _shown_line_boundaries(self):
        current = self._current_line
        for i in range(MAX_LINES):
            if current + i in range(len(self._line_boundaries)):
                yield self._line_boundaries[current + i]

    def render(self):
        shown_line_boundaries = list(self._shown_line_boundaries)
        if not self._first_render:
            RawTerminal.move_cursor_up(MAX_LINES + 1)
        self._first_render = False

        for i in range(MAX_LINES):
            RawTerminal.erase_whole_line()
            if i in range(len(shown_line_boundaries)):
                low, high = shown_line_boundaries[i]
                for idx in range(low, high):
                    if self._status[idx] == STATUS_TYPING:
                        RawTerminal.set_yellow_font()
                    elif self._status[idx] == STATUS_TYPED_WELL:
                        RawTerminal.set_green_font()
                    elif self._status[idx] == STATUS_TYPED_WRONG:
                        RawTerminal.set_red_font()
                    else:
                        RawTerminal.set_default_font()
                    print(self._words[idx], end='')
                    print(end=' ')
            print()
        RawTerminal.erase_whole_line()
        print(f'--- ({self._time_left} s left) ---')
        RawTerminal.erase_whole_line()
        print(self._text_input, end='', flush=True)

    def render_stats(self):
        correct_words = [
            word
            for word, status in zip(self._words, self._status)
            if status == STATUS_TYPED_WELL]
        wrong_words = [
            word
            for word, status in zip(self._words, self._status)
            if status == STATUS_TYPED_WRONG]
        correct_keystrokes = sum(len(word) + 1 for word in correct_words)
        wrong_keystrokes = sum(len(word) + 1 for word in wrong_words)
        total_keystrokes = correct_keystrokes + wrong_keystrokes

        cps = correct_keystrokes / (self._end_time - self._start_time)
        wpm = cps * 60.0 / WORD_LENGTH
        accurracy = (
            correct_keystrokes / self._total_keys_pressed
            if self._total_keys_pressed else 1)

        RawTerminal.erase_whole_line()

        print(f'CPS (chars per second): {cps:.1f}')
        print(f'WPM (words per minute): {wpm:.1f}')

        print(f'Keys pressed:           {total_keystrokes} (', end='')
        RawTerminal.set_green_font()
        print(correct_keystrokes, end='|')
        RawTerminal.set_red_font()
        print(wrong_keystrokes, end='')
        RawTerminal.set_default_font()
        print(')')

        print(f'Total keys pressed:     {self._total_keys_pressed}')
        print(f'Accurracy:              {accurracy:.1%}')

        print(r'Correct words:          ', end='')
        RawTerminal.set_green_font()
        print(len(correct_words), end='')
        RawTerminal.set_default_font()
        print()

        print(r'Wrong words:            ', end='')
        RawTerminal.set_red_font()
        print(len(wrong_words), end='')
        RawTerminal.set_default_font()
        print()

    def backspace_pressed(self):
        self._text_input = self._text_input[:-1]
        self._current_word_keys_pressed += 1

    def key_pressed(self, key):
        self._text_input += key
        self._current_word_keys_pressed += 1

    def word_finished(self):
        self._total_keys_pressed += self._current_word_keys_pressed + 1
        self._current_word_keys_pressed = 0
        self._status[self._current_word] = (
            STATUS_TYPED_WELL
            if self._words[self._current_word] == self._text_input
            else STATUS_TYPED_WRONG)
        self._text_input = ''

        self._current_word += 1
        if self._current_word == len(self._words):
            self.finish()
            return

        self._status[self._current_word] = STATUS_TYPING

    def finish(self):
        self._end_time = time.time()

    def tick(self):
        self._time_left -= 1
        if self._time_left == 0:
            self.finish()


class Game:
    def __init__(self, loop, args):
        corpus = [
            word
            for word in re.split(
                r'\s+', args.corpus_path.read_text(encoding='utf-8'))
            if word]

        self._loop = loop
        self._text = [random.choice(corpus) for _ in range(SAMPLE_SIZE)]
        self._raw_terminal = RawTerminal(loop)
        self._raw_terminal.enable()

    async def run(self):
        state = GameState(self._text)

        async def timer():
            while not state.finished:
                await asyncio.sleep(0.5)
                await asyncio.sleep(0.5)
                state.tick()
                self._raw_terminal.disable()
                state.render()
                self._raw_terminal.enable()
            await self._raw_terminal.input_queue.put(None)

        timer_future = None

        while not state.finished:
            self._raw_terminal.disable()
            state.render()
            self._raw_terminal.enable()
            key = await self._raw_terminal.input_queue.get()

            if key is None:
                state.finish()
                break

            if not timer_future:
                timer_future = asyncio.ensure_future(timer(), loop=self._loop)

            if key == '\x03':
                state.finish()
            elif key == '\x7F':
                state.backspace_pressed()
            elif re.match(r'\s', key):
                state.word_finished()
            else:
                state.key_pressed(key)

        await timer_future
        self._raw_terminal.disable()
        state.render_stats()


async def main(loop):
    args = parse_args()
    game = Game(loop, args)
    await game.run()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))
    loop.close()
