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


class WordStatus(IntEnum):
    """Word state."""

    UNTYPED = 0
    TYPING_WELL = 1
    TYPING_WRONG = 2
    TYPED_WELL = 3
    TYPED_WRONG = 4


@dataclass
class Word:
    """A single word in context of a running game."""

    text: str
    status: WordStatus


@dataclass
class GameSettings:
    """Game settings."""

    corpus: list[str]
    max_time: int
    rigorous_spaces: bool


class GameState:
    """The game state. Does not manipulate itself."""

    def __init__(self, words: list[str], max_time: int) -> None:
        """Initialize self.

        :param words: full list of words to type for this game.
        :param max_time: maximum time for this game.
        """
        self.words = [
            Word(
                text=word,
                status=WordStatus.TYPING_WELL
                if i == 0
                else WordStatus.UNTYPED,
            )
            for i, word in enumerate(words)
        ]
        self.current_word_index = 0
        self.word_input = ""
        self.line_boundaries = divide_lines(words, MAX_COLUMNS)
        self.time_left = max_time
        self.start_time: T.Optional[float] = None
        self.end_time: T.Optional[float] = None
        self.keys_pressed = 0
        self.current_word_keys_pressed = 0
        self.first_render = True
        self.timer_future: T.Optional[asyncio.Task[None]] = None

    @property
    def is_started(self) -> bool:
        """Return whether the game has run out of time.

        :return: whether the game has ended.
        """
        return self.start_time is not None

    @property
    def is_finished(self) -> bool:
        """Return whether the game has run out of time.

        :return: whether the game has ended.
        """
        return self.end_time is not None

    @property
    def current_line(self) -> int:
        """Current line number within all of the game lines."""
        for i, (low, high) in enumerate(self.line_boundaries):
            if self.current_word_index in range(low, high):
                return i
        return len(self.line_boundaries) - 1

    @property
    def current_word(self) -> Word:
        """Currently typed word."""
        return self.words[self.current_word_index]

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


class GameExecutor:
    """Game executor class. Manipulates game state."""

    def __init__(
        self,
        loop: asyncio.events.AbstractEventLoop,
        state: GameState,
        settings: GameSettings,
    ) -> None:
        """Initialize self.

        :param loop: the event loop.
        :param state: game state.
        :param settings: game settings.
        """
        self.loop = loop
        self.state = state
        self.settings = settings

    def start(self) -> None:
        """Start the game timer."""
        self.state.start_time = time.time()

    def finish(self) -> None:
        """Stop the game timer."""
        self.state.end_time = time.time()
        if self.state.timer_future is not None:
            self.state.timer_future.cancel()

    def tick(self) -> None:
        """Decrease time left by 1 second."""
        self.state.time_left -= 1
        if self.state.time_left == 0:
            self.finish()

    def consume_key(self, key: str) -> bool:
        """Consume user key.

        :param key: key to handle.
        """
        if key == "\x03":  # ^C
            self.finish()
        elif key == "\x7F":  # ^H
            self.backspace_pressed()
        elif key == "\x17":  # ^W
            self.word_backspace_pressed()
        elif re.match(r"\s", key):
            if self.state.word_input != "" or self.settings.rigorous_spaces:
                self.word_finished()
        elif len(key) > 1 or ord(key) >= 32:
            self.key_pressed(key)

        if not self.state.is_started:
            self.start()
            self.state.timer_future = asyncio.ensure_future(
                self.timer(), loop=self.loop
            )

        return True

    async def timer(self) -> None:
        """Track the game progress."""
        while not self.state.is_finished:
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            self.tick()
            self.render()

    def update_typing_status(self) -> None:
        """Update the interal list of word states."""
        self.state.current_word.status = (
            WordStatus.TYPING_WELL
            if self.state.current_word.text.startswith(self.state.word_input)
            else WordStatus.TYPING_WRONG
        )

    def backspace_pressed(self) -> None:
        """Delete the last character."""
        self.state.word_input = self.state.word_input[:-1]
        self.state.current_word_keys_pressed += 1
        self.update_typing_status()

    def word_backspace_pressed(self) -> None:
        """Delete the last word."""
        self.state.word_input = ""
        self.state.current_word_keys_pressed += 1
        self.update_typing_status()

    def key_pressed(self, key: str) -> None:
        """Append the given key to the current word.

        :param key: key the user pressed.
        """
        self.state.word_input += key
        self.state.current_word_keys_pressed += 1
        self.update_typing_status()

    def word_finished(self) -> None:
        """Mark the word as finished and either end the game or move on to the
        next word.
        """
        self.state.keys_pressed += self.state.current_word_keys_pressed + 1
        self.state.current_word_keys_pressed = 0
        self.state.current_word.status = (
            WordStatus.TYPED_WELL
            if self.state.current_word.text == self.state.word_input
            else WordStatus.TYPED_WRONG
        )
        self.state.word_input = ""

        self.state.current_word_index += 1
        if self.state.current_word_index == len(self.state.words):
            self.finish()
        else:
            self.state.current_word.status = WordStatus.TYPING_WELL

    def render(self) -> None:
        """Render the game text up to MAX_DISPLAY_LINES together with a timer."""
        shown_line_boundaries = list(self.state.shown_line_boundaries)
        if not self.state.first_render:
            move_cursor_up(MAX_DISPLAY_LINES + 1)
        self.state.first_render = False

        for i in range(MAX_DISPLAY_LINES):
            erase_whole_line()
            if i in range(len(shown_line_boundaries)):
                low, high = shown_line_boundaries[i]
                for idx in range(low, high):
                    set_text_color(
                        {
                            WordStatus.TYPING_WELL: TextColor.YELLOW,
                            WordStatus.TYPING_WRONG: TextColor.RED,
                            WordStatus.TYPED_WELL: TextColor.GREEN,
                            WordStatus.TYPED_WRONG: TextColor.RED,
                        }.get(self.state.words[idx].status, TextColor.DEFAULT)
                    )
                    print(self.state.words[idx].text, end="")
                    print(end=" ")
            print()
        erase_whole_line()
        print("--- ({} s left) ---".format(self.state.time_left))
        erase_whole_line()
        print(self.state.word_input, end="", flush=True)

    def render_stats(self) -> None:
        """Render final game statistics."""
        correct_words = [
            word.text
            for word in self.state.words
            if word.status == WordStatus.TYPED_WELL
        ]
        wrong_words = [
            word.text
            for word in self.state.words
            if word.status == WordStatus.TYPED_WRONG
        ]
        correct_characters = sum(len(word) + 1 for word in correct_words)
        wrong_characters = sum(len(word) + 1 for word in wrong_words)
        total_characters = correct_characters + wrong_characters

        if self.state.end_time is None or self.state.start_time is None:
            cps = 0.0
        else:
            cps = correct_characters / (
                self.state.end_time - self.state.start_time
            )
        wpm = cps * 60.0 / AVG_WORD_LENGTH
        accuracy = (
            correct_characters / self.state.keys_pressed
            if self.state.keys_pressed
            else 1
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
        print("Keys pressed:           {}".format(self.state.keys_pressed))
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


async def run_game(
    loop: asyncio.events.AbstractEventLoop,
    input_handler: TerminalInputHandler,
    settings: GameSettings,
) -> None:
    """Run the game loop.

    :param loop: the event loop.
    :param input_handler: input handler instance.
    :param settings: game settings.
    """
    all_words = [random.choice(settings.corpus) for _i in range(SAMPLE_SIZE)]
    state = GameState(all_words, settings.max_time)
    executor = GameExecutor(loop, state, settings)

    while not state.is_finished:
        executor.render()
        try:
            key = input_handler.input_queue.get_nowait()
        except asyncio.QueueEmpty:
            await asyncio.sleep(0.05)
        else:
            executor.consume_key(key)

    assert state.timer_future is not None
    try:
        await state.timer_future
    except asyncio.CancelledError:
        pass
    executor.render_stats()
