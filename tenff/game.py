import asyncio
import random
import re
import shutil
import time
import typing as T
from pathlib import Path

from tenff.raw_terminal import RawTerminal
from tenff.util import divide_lines

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
    def __init__(self, words: list[str], max_time: int) -> None:
        self._words = words
        self._current_word = 0
        self._text_input = ""
        self._status = [STATUS_TYPING_WELL] + [
            STATUS_UNTYPED for _word in words[1:]
        ]
        self._line_boundaries = divide_lines(words, MAX_COLUMNS)
        self._time_left = max_time
        self._start_time = time.time()
        self._end_time: T.Optional[float] = None
        self._keys_pressed = 0
        self._current_word_keys_pressed = 0
        self._first_render = True

    @property
    def finished(self) -> bool:
        return self._end_time is not None

    @property
    def _current_line(self) -> int:
        for i, (low, high) in enumerate(self._line_boundaries):
            if self._current_word in range(low, high):
                return i
        return len(self._line_boundaries) - 1

    @property
    def _shown_line_boundaries(self) -> T.Iterable[tuple[int, int]]:
        current = self._current_line
        for i in range(MAX_LINES):
            if current + i in range(len(self._line_boundaries)):
                yield self._line_boundaries[current + i]

    def render(self) -> None:
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
                    print(self._words[idx], end="")
                    print(end=" ")
            print()
        RawTerminal.erase_whole_line()
        print("--- ({} s left) ---".format(self._time_left))
        RawTerminal.erase_whole_line()
        print(self._text_input, end="", flush=True)

    def render_stats(self) -> None:
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

        if self._end_time is None:
            cps = 0.0
        else:
            cps = correct_characters / (self._end_time - self._start_time)
        wpm = cps * 60.0 / WORD_LENGTH
        accuracy = (
            correct_characters / self._keys_pressed
            if self._keys_pressed
            else 1
        )

        RawTerminal.erase_whole_line()

        print("CPS (chars per second): {:.1f}".format(cps))
        print("WPM (words per minute): {:.1f}".format(wpm))

        print("Characters typed:       {} (".format(total_characters), end="")
        RawTerminal.set_green_font()
        print(correct_characters, end="|")
        RawTerminal.set_red_font()
        print(wrong_characters, end="")
        RawTerminal.set_default_font()
        print(")")

        print("Keys pressed:           {}".format(self._keys_pressed))
        print("Accuracy:               {:.1%}".format(accuracy))

        print(r"Correct words:          ", end="")
        RawTerminal.set_green_font()
        print(len(correct_words), end="")
        RawTerminal.set_default_font()
        print()

        print(r"Wrong words:            ", end="")
        RawTerminal.set_red_font()
        print(len(wrong_words), end="")
        RawTerminal.set_default_font()
        print()

    def started(self) -> None:
        self._start_time = time.time()

    def backspace_pressed(self) -> None:
        self._text_input = self._text_input[:-1]
        self._current_word_keys_pressed += 1
        self._update_typing_status()

    def word_backspace_pressed(self) -> None:
        self._text_input = ""
        self._current_word_keys_pressed += 1
        self._update_typing_status()

    def key_pressed(self, key: str) -> None:
        self._text_input += key
        self._current_word_keys_pressed += 1
        self._update_typing_status()

    def word_finished(self) -> None:
        self._keys_pressed += self._current_word_keys_pressed + 1
        self._current_word_keys_pressed = 0
        self._status[self._current_word] = (
            STATUS_TYPED_WELL
            if self._words[self._current_word] == self._text_input
            else STATUS_TYPED_WRONG
        )
        self._text_input = ""

        self._current_word += 1
        if self._current_word == len(self._words):
            self.finish()
            return

        self._status[self._current_word] = STATUS_TYPING_WELL

    def finish(self) -> None:
        self._end_time = time.time()

    def tick(self) -> None:
        self._time_left -= 1
        if self._time_left == 0:
            self.finish()

    def _update_typing_status(self) -> None:
        self._status[self._current_word] = (
            STATUS_TYPING_WELL
            if self._words[self._current_word].startswith(self._text_input)
            else STATUS_TYPING_WRONG
        )


class Game:
    def __init__(
        self,
        loop: asyncio.events.AbstractEventLoop,
        corpus_path: Path,
        max_time: int,
        rigorous_spaces: bool,
    ) -> None:
        corpus = [
            word
            for word in re.split(
                r"\s+", corpus_path.read_text(encoding="utf-8")
            )
            if word
        ]

        self._max_time = max_time
        self._all_words = [random.choice(corpus) for _i in range(SAMPLE_SIZE)]
        self._rigorous_spaces = rigorous_spaces

        self._loop = loop
        self._raw_terminal = RawTerminal(loop)
        self._raw_terminal.enable()

    async def run(self) -> None:
        state = GameState(self._all_words, self._max_time)

        async def timer() -> None:
            while not state.finished:
                await asyncio.sleep(0.5)
                await asyncio.sleep(0.5)
                state.tick()
                self._raw_terminal.disable()
                state.render()
                self._raw_terminal.enable()
            await self._raw_terminal.input_queue.put(None)

        timer_future: T.Optional[T.Awaitable[T.Any]] = None

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

            if key == "\x03":
                state.finish()
            elif key == "\x7F":
                state.backspace_pressed()
            elif key in "\x17":
                state.word_backspace_pressed()
            elif re.match(r"\s", key):
                if state._text_input != "" or self._rigorous_spaces:
                    state.word_finished()
            elif len(key) > 1 or ord(key) >= 32:
                state.key_pressed(key)

        assert timer_future is not None
        await timer_future
        self._raw_terminal.disable()
        state.render_stats()
