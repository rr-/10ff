"""Game logic."""
import asyncio
import random
import re
import shutil
import time
import typing as T
from dataclasses import dataclass
from enum import IntEnum

from tenff.terminal import (
    TerminalInputHandler,
    TextColor,
    erase_whole_line,
    move_cursor_up,
    set_text_color,
)
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


@dataclass
class GameSettings:
    """Game settings."""

    corpus: list[str]
    max_time: int
    rigorous_spaces: bool


class GameState:
    """The game state and state manipulation methods."""

    def __init__(self, words: list[str], max_time: int) -> None:
        """Initialize self.

        :param words: full list of words to type for this game.
        :param max_time: maximum time for this game.
        """
        self.words = words
        self.current_word = 0
        self.word_input = ""
        self.word_states = [WordState.TYPING_WELL] + [
            WordState.UNTYPED for _word in words[1:]
        ]
        self.line_boundaries = divide_lines(words, MAX_COLUMNS)
        self.time_left = max_time
        self.start_time = time.time()
        self.end_time: T.Optional[float] = None
        self.keys_pressed = 0
        self.current_word_keys_pressed = 0
        self.first_render = True

    @property
    def is_finished(self) -> bool:
        """Return whether the game has run out of time.

        :return: whether the game has ended.
        """
        return self.end_time is not None

    @property
    def current_line(self) -> int:
        """Current line within all of the game lines."""
        for i, (low, high) in enumerate(self.line_boundaries):
            if self.current_word in range(low, high):
                return i
        return len(self.line_boundaries) - 1

    @property
    def shown_line_boundaries(self) -> T.Iterable[tuple[int, int]]:
        """Line boundaries within viewport.

        :return: list of tuples with low and high indices of the game words
                 to render.
        """
        current = self.current_line
        for i in range(MAX_DISPLAY_LINES):
            if current + i in range(len(self.line_boundaries)):
                yield self.line_boundaries[current + i]

    def start(self) -> None:
        """Start the game timer."""
        self.start_time = time.time()

    def backspace_pressed(self) -> None:
        """Delete the last character."""
        self.word_input = self.word_input[:-1]
        self.current_word_keys_pressed += 1
        self.update_typing_status()

    def word_backspace_pressed(self) -> None:
        """Delete the last word."""
        self.word_input = ""
        self.current_word_keys_pressed += 1
        self.update_typing_status()

    def key_pressed(self, key: str) -> None:
        """Append the given key to the current word.

        :param key: key the user pressed.
        """
        self.word_input += key
        self.current_word_keys_pressed += 1
        self.update_typing_status()

    def word_finished(self) -> None:
        """Mark the word as finished and either end the game or move on to the
        next word.
        """
        self.keys_pressed += self.current_word_keys_pressed + 1
        self.current_word_keys_pressed = 0
        self.word_states[self.current_word] = (
            WordState.TYPED_WELL
            if self.words[self.current_word] == self.word_input
            else WordState.TYPED_WRONG
        )
        self.word_input = ""

        self.current_word += 1
        if self.current_word == len(self.words):
            self.finish()
            return

        self.word_states[self.current_word] = WordState.TYPING_WELL

    def finish(self) -> None:
        """Stop the game."""
        self.end_time = time.time()

    def tick(self) -> None:
        """Decrease time left by 1 second."""
        self.time_left -= 1
        if self.time_left == 0:
            self.finish()

    def update_typing_status(self) -> None:
        """Update the interal list of word states."""
        self.word_states[self.current_word] = (
            WordState.TYPING_WELL
            if self.words[self.current_word].startswith(self.word_input)
            else WordState.TYPING_WRONG
        )

    def render(self) -> None:
        """Render the game text up to MAX_DISPLAY_LINES together with a timer."""
        shown_line_boundaries = list(self.shown_line_boundaries)
        if not self.first_render:
            move_cursor_up(MAX_DISPLAY_LINES + 1)
        self.first_render = False

        for i in range(MAX_DISPLAY_LINES):
            erase_whole_line()
            if i in range(len(shown_line_boundaries)):
                low, high = shown_line_boundaries[i]
                for idx in range(low, high):
                    set_text_color(
                        {
                            WordState.TYPING_WELL: TextColor.YELLOW,
                            WordState.TYPING_WRONG: TextColor.RED,
                            WordState.TYPED_WELL: TextColor.GREEN,
                            WordState.TYPED_WRONG: TextColor.RED,
                        }.get(self.word_states[idx], TextColor.DEFAULT)
                    )
                    print(self.words[idx], end="")
                    print(end=" ")
            print()
        erase_whole_line()
        print("--- ({} s left) ---".format(self.time_left))
        erase_whole_line()
        print(self.word_input, end="", flush=True)

    def render_stats(self) -> None:
        """Render final game statistics."""
        correct_words = [
            word
            for word, status in zip(self.words, self.word_states)
            if status == WordState.TYPED_WELL
        ]
        wrong_words = [
            word
            for word, status in zip(self.words, self.word_states)
            if status == WordState.TYPED_WRONG
        ]
        correct_characters = sum(len(word) + 1 for word in correct_words)
        wrong_characters = sum(len(word) + 1 for word in wrong_words)
        total_characters = correct_characters + wrong_characters

        if self.end_time is None:
            cps = 0.0
        else:
            cps = correct_characters / (self.end_time - self.start_time)
        wpm = cps * 60.0 / AVG_WORD_LENGTH
        accuracy = (
            correct_characters / self.keys_pressed if self.keys_pressed else 1
        )

        erase_whole_line()

        print("CPS (chars per second): {:.1f}".format(cps))
        erase_whole_line()
        print("WPM (words per minute): {:.1f}".format(wpm))

        erase_whole_line()
        print("Characters typed:       {} (".format(total_characters), end="")
        set_text_color(TextColor.GREEN)
        print(correct_characters, end="|")
        set_text_color(TextColor.RED)
        print(wrong_characters, end="")
        set_text_color(TextColor.DEFAULT)
        print(")")

        erase_whole_line()
        print("Keys pressed:           {}".format(self.keys_pressed))
        erase_whole_line()
        print("Accuracy:               {:.1%}".format(accuracy))

        erase_whole_line()
        print(r"Correct words:          ", end="")
        set_text_color(TextColor.GREEN)
        print(len(correct_words), end="")
        set_text_color(TextColor.DEFAULT)
        print()

        erase_whole_line()
        print(r"Wrong words:            ", end="")
        set_text_color(TextColor.RED)
        print(len(wrong_words), end="")
        set_text_color(TextColor.DEFAULT)

        erase_whole_line()
        print()


class Game:
    """Game executor."""

    def __init__(
        self,
        loop: asyncio.events.AbstractEventLoop,
        input_handler: TerminalInputHandler,
        settings: GameSettings,
    ) -> None:
        """Initialize self.

        :param loop: the event loop.
        :param input_handler: input handler instance.
        :param settings: game settings.
        """
        self.loop = loop
        self.input_handler = input_handler
        self.settings = settings

    async def run(self) -> None:
        """Run the game."""
        all_words = [
            random.choice(self.settings.corpus) for _i in range(SAMPLE_SIZE)
        ]
        state = GameState(all_words, self.settings.max_time)

        async def timer() -> None:
            while not state.is_finished:
                await asyncio.sleep(0.5)
                await asyncio.sleep(0.5)
                state.tick()
                state.render()
            await self.input_handler.input_queue.put(None)

        timer_future: T.Optional[T.Awaitable[T.Any]] = None

        while not state.is_finished:
            state.render()
            key = await self.input_handler.input_queue.get()

            if key is None:
                state.finish()
                break

            if not timer_future:
                state.start()
                timer_future = asyncio.ensure_future(timer(), loop=self.loop)

            if key == "\x03":
                state.finish()
            elif key == "\x7F":
                state.backspace_pressed()
            elif key in "\x17":
                state.word_backspace_pressed()
            elif re.match(r"\s", key):
                if state.word_input != "" or self.settings.rigorous_spaces:
                    state.word_finished()
            elif len(key) > 1 or ord(key) >= 32:
                state.key_pressed(key)

        assert timer_future is not None
        await timer_future
        state.render_stats()
