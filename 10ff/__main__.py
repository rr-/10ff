#!/usr/bin/env python3
import re
import sys
import random
import shutil
import argparse
import pathlib
import readchar

MAX_COLUMNS = min(shutil.get_terminal_size().columns, 80)
MAX_SHOWN_LINES = 2
SAMPLE_SIZE = 1000

STATUS_UNTYPED = 0
STATUS_TYPING = 1
STATUS_TYPED_WELL = 2
STATUS_TYPED_BAD = 3


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


class GameState:
    def __init__(self, words):
        self.words = words
        self.current_word = 0
        self.text_input = ''
        self.status = [STATUS_UNTYPED for _ in words]
        self.status[self.current_word] = STATUS_TYPING
        self.line_boundaries = divide_lines(words)
        self.max_shown_word = 0
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
        for i in range(MAX_SHOWN_LINES):
            if current + i in range(len(self.line_boundaries)):
                yield self.line_boundaries[current + i]

    def render(self):
        shown_line_boundaries = list(self.shown_line_boundaries)
        if not self._first_run:
            sys.stdout.write(f'\x1B[{MAX_SHOWN_LINES + 1}F')
        self._first_run = False

        for i in range(MAX_SHOWN_LINES):
            sys.stdout.write('\x1B[K')
            if i in range(len(shown_line_boundaries)):
                low, high = shown_line_boundaries[i]
                for idx in range(low, high):
                    if self.status[idx] == STATUS_TYPING:
                        sys.stdout.write('\x1B[33;1m')
                    elif self.status[idx] == STATUS_TYPED_WELL:
                        sys.stdout.write('\x1B[32;1m')
                    elif self.status[idx] == STATUS_TYPED_BAD:
                        sys.stdout.write('\x1B[31;1m')
                    else:
                        sys.stdout.write('\x1B[39m')
                    print(self.words[idx], end='')
                    sys.stdout.write('\x1B[39m')
                    print(end=' ')
            print()
        print('---')
        sys.stdout.write('\x1B[K')
        print(self.text_input, end='', flush=True)

    def backspace_pressed(self):
        self.text_input = self.text_input[:-1]

    def key_pressed(self, key):
        self.text_input += key

    def word_finished(self):
        self.status[self.current_word] = (
            STATUS_TYPED_WELL
            if self.words[self.current_word] == self.text_input
            else STATUS_TYPED_BAD)
        self.text_input = ''

        self.current_word += 1
        if self.current_word == len(self.words):
            return True

        self.status[self.current_word] = STATUS_TYPING
        return False


class Game:
    def __init__(self, args):
        corpus = [
            word
            for word in re.split(
                r'\s+', args.corpus_path.read_text(encoding='utf-8'))
            if word]

        self._text = [random.choice(corpus) for _ in range(SAMPLE_SIZE)]

    def run(self):
        state = GameState(self._text)
        game_over = False

        while not game_over:
            state.render()
            key = readchar.readkey()

            if key == '\x03':
                game_over = True
            elif key == '\x7F':
                state.backspace_pressed()
            elif re.match(r'\s', key):
                game_over = state.word_finished()
            else:
                state.key_pressed(key)


def main():
    args = parse_args()
    game = Game(args)
    game.run()


if __name__ == '__main__':
    main()
