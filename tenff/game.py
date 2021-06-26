"""Game logic."""
import asyncio
import random
import re
import shutil
import time
import typing as T
from enum import IntEnum
from pathlib import Path

from tenff.raw_terminal import RawTerminal
from tenff.util import divide_lines

MAX_COLUMNS = min(shutil.get_terminal_size().columns, 80)
MAX_DISPLAY_LINES = 2
SAMPLE_SIZE = 1000
AVG_WORD_LENGTH = 5


class WordState(IntEnum):
    """Word state."""

    UNTYPED = 0
    TYPING_WELL = 1
    TYPING_WRONG = 2
    TYPED_WELL = 3
    TYPED_WRONG = 4


class GameState:
    """The game state and state manipulation methods."""

    def __init__(self, words: list[str], max_time: int) -> None:
        """Initialize self.

        :param words: full list of words to type for this game.
        :param max_time: maximum time for this game.
        """
        self._words = words
        self._current_word = 0
        self._word_input = ""
        self._word_states = [WordState.TYPING_WELL] + [
            WordState.UNTYPED for _word in words[1:]
        ]
        self._line_boundaries = divide_lines(words, MAX_COLUMNS)
        self._time_left = max_time
        self._start_time = time.time()
        self._end_time: T.Optional[float] = None
        self._keys_pressed = 0
        self._current_word_keys_pressed = 0
        self._first_render = True

    @property
    def is_finished(self) -> bool:
        """Return whether the game has run out of time.

        :return: whether the game has ended.
        """
        return self._end_time is not None

    @property
    def _current_line(self) -> int:
        """Current line within all of the game lines."""
        for i, (low, high) in enumerate(self._line_boundaries):
            if self._current_word in range(low, high):
                return i
        return len(self._line_boundaries) - 1

    @property
    def _shown_line_boundaries(self) -> T.Iterable[tuple[int, int]]:
        """Line boundaries within viewport.

        :return: list of tuples with low and high indices of the game words
                 to render.
        """
        current = self._current_line
        for i in range(MAX_DISPLAY_LINES):
            if current + i in range(len(self._line_boundaries)):
                yield self._line_boundaries[current + i]

    def start(self) -> None:
        """Start the game timer."""
        self._start_time = time.time()

    def backspace_pressed(self) -> None:
        """Delete the last character."""
        self._word_input = self._word_input[:-1]
        self._current_word_keys_pressed += 1
        self._update_typing_status()

    def word_backspace_pressed(self) -> None:
        """Delete the last word."""
        self._word_input = ""
        self._current_word_keys_pressed += 1
        self._update_typing_status()

    def key_pressed(self, key: str) -> None:
        """Append the given key to the current word.

        :param key: key the user pressed.
        """
        self._word_input += key
        self._current_word_keys_pressed += 1
        self._update_typing_status()

    def word_finished(self) -> None:
        """Mark the word as finished and either end the game or move on to the
        next word.
        """
        self._keys_pressed += self._current_word_keys_pressed + 1
        self._current_word_keys_pressed = 0
        self._word_states[self._current_word] = (
            WordState.TYPED_WELL
            if self._words[self._current_word] == self._word_input
            else WordState.TYPED_WRONG
        )
        self._word_input = ""

        self._current_word += 1
        if self._current_word == len(self._words):
            self.finish()
            return

        self._word_states[self._current_word] = WordState.TYPING_WELL

    def finish(self) -> None:
        """Stop the game."""
        self._end_time = time.time()

    def tick(self) -> None:
        """Decrease time left by 1 second."""
        self._time_left -= 1
        if self._time_left == 0:
            self.finish()

    def _update_typing_status(self) -> None:
        """Update the interal list of word states."""
        self._word_states[self._current_word] = (
            WordState.TYPING_WELL
            if self._words[self._current_word].startswith(self._word_input)
            else WordState.TYPING_WRONG
        )

    def render(self) -> None:
        """Render the game text up to MAX_DISPLAY_LINES together with a timer."""
        shown_line_boundaries = list(self._shown_line_boundaries)
        if not self._first_render:
            RawTerminal.move_cursor_up(MAX_DISPLAY_LINES + 1)
        self._first_render = False

        for i in range(MAX_DISPLAY_LINES):
            RawTerminal.erase_whole_line()
            if i in range(len(shown_line_boundaries)):
                low, high = shown_line_boundaries[i]
                for idx in range(low, high):
                    if self._word_states[idx] == WordState.TYPING_WELL:
                        RawTerminal.set_yellow_font()
                    elif self._word_states[idx] == WordState.TYPING_WRONG:
                        RawTerminal.set_red_font()
                    elif self._word_states[idx] == WordState.TYPED_WELL:
                        RawTerminal.set_green_font()
                    elif self._word_states[idx] == WordState.TYPED_WRONG:
                        RawTerminal.set_red_font()
                    else:
                        RawTerminal.set_default_font()
                    print(self._words[idx], end="")
                    print(end=" ")
            print()
        RawTerminal.erase_whole_line()
        print("--- ({} s left) ---".format(self._time_left))
        RawTerminal.erase_whole_line()
        print(self._word_input, end="", flush=True)

    def render_stats(self) -> None:
        """Render final game statistics."""
        correct_words = [
            word
            for word, status in zip(self._words, self._word_states)
            if status == WordState.TYPED_WELL
        ]
        wrong_words = [
            word
            for word, status in zip(self._words, self._word_states)
            if status == WordState.TYPED_WRONG
        ]
        correct_characters = sum(len(word) + 1 for word in correct_words)
        wrong_characters = sum(len(word) + 1 for word in wrong_words)
        total_characters = correct_characters + wrong_characters

        if self._end_time is None:
            cps = 0.0
        else:
            cps = correct_characters / (self._end_time - self._start_time)
        wpm = cps * 60.0 / AVG_WORD_LENGTH
        accuracy = (
            correct_characters / self._keys_pressed
            if self._keys_pressed
            else 1
        )

        RawTerminal.erase_whole_line()

        print("CPS (chars per second): {:.1f}".format(cps))
        RawTerminal.erase_whole_line()
        print("WPM (words per minute): {:.1f}".format(wpm))

        RawTerminal.erase_whole_line()
        print("Characters typed:       {} (".format(total_characters), end="")
        RawTerminal.set_green_font()
        print(correct_characters, end="|")
        RawTerminal.set_red_font()
        print(wrong_characters, end="")
        RawTerminal.set_default_font()
        print(")")

        RawTerminal.erase_whole_line()
        print("Keys pressed:           {}".format(self._keys_pressed))
        RawTerminal.erase_whole_line()
        print("Accuracy:               {:.1%}".format(accuracy))

        RawTerminal.erase_whole_line()
        print(r"Correct words:          ", end="")
        RawTerminal.set_green_font()
        print(len(correct_words), end="")
        RawTerminal.set_default_font()
        print()

        RawTerminal.erase_whole_line()
        print(r"Wrong words:            ", end="")
        RawTerminal.set_red_font()
        print(len(wrong_words), end="")
        RawTerminal.set_default_font()

        RawTerminal.erase_whole_line()
        print()


class Game:
    """Game executor."""

    def __init__(
        self,
        loop: asyncio.events.AbstractEventLoop,
        input_queue: asyncio.Queue[T.Optional[str]],
        corpus_path: Path,
        max_time: int,
        rigorous_spaces: bool,
    ) -> None:
        """Initialize self.

        :param loop: the event loop.
        :param input_queue: queue that receives user keypresses
        :param corpus_path: path to the corpus.
        :param max_time: maximum time to run the game.
        :param rigorous_spaces: whether a bad space means a mistake.
        """
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
        self._input_queue = input_queue

    async def run(self) -> None:
        """Run the game."""
        state = GameState(self._all_words, self._max_time)

        async def timer() -> None:
            while not state.is_finished:
                await asyncio.sleep(0.5)
                await asyncio.sleep(0.5)
                state.tick()
                state.render()
            await self._input_queue.put(None)

        timer_future: T.Optional[T.Awaitable[T.Any]] = None

        while not state.is_finished:
            state.render()
            key = await self._input_queue.get()

            if key is None:
                state.finish()
                break

            if not timer_future:
                state.start()
                timer_future = asyncio.ensure_future(timer(), loop=self._loop)

            if key == "\x03":
                state.finish()
            elif key == "\x7F":
                state.backspace_pressed()
            elif key in "\x17":
                state.word_backspace_pressed()
            elif re.match(r"\s", key):
                if state._word_input != "" or self._rigorous_spaces:
                    state.word_finished()
            elif len(key) > 1 or ord(key) >= 32:
                state.key_pressed(key)

        assert timer_future is not None
        await timer_future
        state.render_stats()
