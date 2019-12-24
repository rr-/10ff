import asyncio
import random
import re
import shutil
import time

from .raw_terminal import RawTerminal
from .util import divide_lines

MAX_COLUMNS = min(shutil.get_terminal_size().columns, 80)
MAX_LINES = 2
SAMPLE_SIZE = 1000
WORD_LENGTH = 5

STATUS_UNTYPED = 0
STATUS_TYPING_WELL = 1
STATUS_TYPING_WRONG = 2
STATUS_TYPED_WELL = 3
STATUS_TYPED_WRONG = 4


class GameState:
    def __init__(self, words, max_time):
        self._words = words
        self._current_word = 0
        self._text_input = ''
        self._status = (
            [STATUS_TYPING_WELL] + [STATUS_UNTYPED for _ in words[1:]]
        )
        self._line_boundaries = divide_lines(words, MAX_COLUMNS)
        self._time_left = max_time
        self._start_time = time.time()
        self._end_time = None
        self._keys_pressed = 0
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
                    if self._status[idx] == STATUS_TYPING_WELL:
                        RawTerminal.set_yellow_font()
                    elif self._status[idx] == STATUS_TYPING_WRONG:
                        RawTerminal.set_red_font()
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
        print('--- ({} s left) ---'.format(self._time_left))
        RawTerminal.erase_whole_line()
        print(self._text_input, end='', flush=True)

    def render_stats(self):
        correct_words = [
            word
            for word, status in zip(self._words, self._status)
            if status == STATUS_TYPED_WELL
        ]
        wrong_words = [
            word
            for word, status in zip(self._words, self._status)
            if status == STATUS_TYPED_WRONG
        ]
        correct_characters = sum(len(word) + 1 for word in correct_words)
        wrong_characters = sum(len(word) + 1 for word in wrong_words)
        total_characters = correct_characters + wrong_characters

        cps = correct_characters / (self._end_time - self._start_time)
        wpm = cps * 60.0 / WORD_LENGTH
        accuracy = (
            correct_characters / self._keys_pressed
            if self._keys_pressed else 1
        )

        RawTerminal.erase_whole_line()

        print('CPS (chars per second): {:.1f}'.format(cps))
        print('WPM (words per minute): {:.1f}'.format(wpm))

        print('Characters typed:       {} ('.format(total_characters), end='')
        RawTerminal.set_green_font()
        print(correct_characters, end='|')
        RawTerminal.set_red_font()
        print(wrong_characters, end='')
        RawTerminal.set_default_font()
        print(')')

        print('Keys pressed:           {}'.format(self._keys_pressed))
        print('Accuracy:               {:.1%}'.format(accuracy))

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

    def started(self):
        self._start_time = time.time()

    def backspace_pressed(self):
        self._text_input = self._text_input[:-1]
        self._current_word_keys_pressed += 1
        self._update_typing_status()

    def key_pressed(self, key):
        self._text_input += key
        self._current_word_keys_pressed += 1
        self._update_typing_status()

    def word_finished(self):
        self._keys_pressed += self._current_word_keys_pressed + 1
        self._current_word_keys_pressed = 0
        self._status[self._current_word] = (
            STATUS_TYPED_WELL
            if self._words[self._current_word] == self._text_input
            else STATUS_TYPED_WRONG
        )
        self._text_input = ''

        self._current_word += 1
        if self._current_word == len(self._words):
            self.finish()
            return

        self._status[self._current_word] = STATUS_TYPING_WELL

    def finish(self):
        self._end_time = time.time()

    def tick(self):
        self._time_left -= 1
        if self._time_left == 0:
            self.finish()

    def _update_typing_status(self):
        self._status[self._current_word] = (
            STATUS_TYPING_WELL
            if self._words[self._current_word].startswith(self._text_input)
            else STATUS_TYPING_WRONG
        )


class Game:
    def __init__(self, loop, args):
        corpus = [
            word
            for word in re.split(
                r'\s+', args.corpus_path.read_text(encoding='utf-8')
            )
            if word
        ]

        self._max_time = args.time
        self._text = [random.choice(corpus) for _ in range(SAMPLE_SIZE)]

        self._loop = loop
        self._raw_terminal = RawTerminal(loop)
        self._raw_terminal.enable()

    async def run(self):
        state = GameState(self._text, self._max_time)

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
                state.started()
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
