#!/usr/bin/env python3
import re
import sys
import random
import shutil
import argparse
import pathlib
import asyncio
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
        '-c', '--corpus', type=pathlib.Path, dest='corpus_path', required=True)
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
    def __init__(self):
        self._fd = sys.stdin.fileno()

    def enable(self):
        self._old_settings = termios.tcgetattr(self._fd)
        tty.setraw(self._fd)

    def disable(self):
        termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)


class GameState:
    def __init__(self, words):
        self.words = words
        self.current_word = 0
        self.text_input = ''
        self.status = [STATUS_UNTYPED for _ in words]
        self.status[self.current_word] = STATUS_TYPING
        self.line_boundaries = divide_lines(words)
        self.max_shown_word = 0
        self.time_left = MAX_TIME
        self.game_over = False
        self.total_keys_pressed = 0
        self.current_word_keys_pressed = 0
        self._first_run = True

    @property
    def current_line(self):
        for i, (low, high) in enumerate(self.line_boundaries):
            if self.current_word in range(low, high):
                return i
        assert False, 'Word out of bounds'

    @property
    def shown_line_boundaries(self):
        current = self.current_line
        for i in range(MAX_LINES):
            if current + i in range(len(self.line_boundaries)):
                yield self.line_boundaries[current + i]

    def render(self):
        shown_line_boundaries = list(self.shown_line_boundaries)
        if not self._first_run:
            sys.stdout.write(f'\x1B[{MAX_LINES + 1}F')
        self._first_run = False

        for i in range(MAX_LINES):
            sys.stdout.write('\x1B[K')
            if i in range(len(shown_line_boundaries)):
                low, high = shown_line_boundaries[i]
                for idx in range(low, high):
                    if self.status[idx] == STATUS_TYPING:
                        sys.stdout.write('\x1B[33;1m')
                    elif self.status[idx] == STATUS_TYPED_WELL:
                        sys.stdout.write('\x1B[32;1m')
                    elif self.status[idx] == STATUS_TYPED_WRONG:
                        sys.stdout.write('\x1B[31;1m')
                    else:
                        sys.stdout.write('\x1B[39m')
                    print(self.words[idx], end='')
                    sys.stdout.write('\x1B[39m')
                    print(end=' ')
            print()
        sys.stdout.write('\x1B[K')
        print(f'--- ({self.time_left} s left) ---')
        sys.stdout.write('\x1B[K')
        print(self.text_input, end='', flush=True)

    def render_stats(self):
        correct_words = [
            word
            for word, status in zip(self.words, self.status)
            if status == STATUS_TYPED_WELL]
        wrong_words = [
            word
            for word, status in zip(self.words, self.status)
            if status == STATUS_TYPED_WRONG]
        correct_keystrokes = sum(len(word) + 1 for word in correct_words)
        wrong_keystrokes = sum(len(word) + 1 for word in wrong_words)
        total_keystrokes = correct_keystrokes + wrong_keystrokes

        cps = correct_keystrokes / MAX_TIME
        wpm = cps * 60.0 / WORD_LENGTH
        accurracy = (
            correct_keystrokes / self.total_keys_pressed
            if self.total_keys_pressed else 1)

        sys.stdout.write('\x1B[999D\x1B[K')

        print(f'CPS (chars per second): {cps}')
        print(f'WPM (words per minute): {wpm}')

        print(f'Keys pressed:           {total_keystrokes} (', end='')
        sys.stdout.write('\x1B[32;1m')
        print(correct_keystrokes, end='|')
        sys.stdout.write('\x1B[31;1m')
        print(wrong_keystrokes, end='')
        sys.stdout.write('\x1B[39m')
        print(')')

        print(f'Total keys pressed:     {self.total_keys_pressed}')
        print(f'Accurracy:              {accurracy:.02%}')

        print(r'Correct words:          ', end='')
        sys.stdout.write('\x1B[32;1m')
        print(len(correct_words), end='')
        sys.stdout.write('\x1B[39m')
        print()

        print(r'Wrong words:            ', end='')
        sys.stdout.write('\x1B[31;1m')
        print(len(wrong_words), end='')
        sys.stdout.write('\x1B[39m')
        print()

    def backspace_pressed(self):
        self.text_input = self.text_input[:-1]
        self.current_word_keys_pressed += 1

    def key_pressed(self, key):
        self.text_input += key
        self.current_word_keys_pressed += 1

    def word_finished(self):
        self.total_keys_pressed += self.current_word_keys_pressed + 1
        self.current_word_keys_pressed = 0
        self.status[self.current_word] = (
            STATUS_TYPED_WELL
            if self.words[self.current_word] == self.text_input
            else STATUS_TYPED_WRONG)
        self.text_input = ''

        self.current_word += 1
        if self.current_word == len(self.words):
            self.game_over = True
            return

        self.status[self.current_word] = STATUS_TYPING

    def tick(self):
        self.time_left -= 1
        if self.time_left == 0:
            self.game_over = True


class Game:
    def __init__(self, loop, args):
        corpus = [
            word
            for word in re.split(
                r'\s+', args.corpus_path.read_text(encoding='utf-8'))
            if word]

        self._loop = loop
        self._text = [random.choice(corpus) for _ in range(SAMPLE_SIZE)]
        self._raw_terminal = RawTerminal()
        self._raw_terminal.enable()

        self._queue = asyncio.Queue(loop=self._loop)
        self._loop.add_reader(sys.stdin, self._got_input)

    async def run(self):
        state = GameState(self._text)

        async def timer():
            while not state.game_over:
                await asyncio.sleep(1)
                state.tick()
                self._raw_terminal.disable()
                state.render()
                self._raw_terminal.enable()

        timer_started = False

        while not state.game_over:
            self._raw_terminal.disable()
            state.render()
            self._raw_terminal.enable()
            key = await self._queue.get()

            if not timer_started:
                asyncio.ensure_future(timer(), loop=self._loop)
                timer_started = True

            if key == '\x03':
                break
            elif key == '\x7F':
                state.backspace_pressed()
            elif re.match(r'\s', key):
                state.word_finished()
            else:
                state.key_pressed(key)

        self._raw_terminal.disable()
        state.render_stats()

    def _got_input(self):
        asyncio.ensure_future(
            self._queue.put(sys.stdin.read(1)), loop=self._loop)


async def main(loop):
    args = parse_args()
    game = Game(loop, args)
    await game.run()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))
    loop.close()
