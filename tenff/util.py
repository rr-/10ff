"""Miscellaneous utility functions."""
import re
from pathlib import Path

CORPORA_PATH = Path(__file__).parent / "data"


def get_corpus_path(corpus: str) -> Path:
    """Get path to the given corpus name. If the name does not resolve to a
    built-in corpus, treat it as a direct path.

    :param corpus: the corpus name.
    :return: path to the corpus with the given name or path.
    """
    corpus_path = CORPORA_PATH / (corpus + ".txt")
    if corpus_path.exists():
        return corpus_path
    return Path(corpus)


def parse_corpus(corpus_path: Path) -> list[str]:
    """Read given path and return all words within it.

    :param corpus_path: path to the corpus.
    :return: list of words within the file.
    """
    return [
        word
        for word in re.split(r"\s+", corpus_path.read_text(encoding="utf-8"))
        if word
    ]


def divide_lines(words: list[str], max_columns: int) -> list[tuple[int, int]]:
    """Divide words into lines.

    :param max_columns: maximum columns that can fit in a single line.
    :return: list of lines with indices of the input text.
    """
    lines = []
    words_left = words[:]
    while len(words_left):
        current_line = ""
        low = len(words) - len(words_left)
        while len(words_left):
            word = words_left[0]
            new_line = " ".join((current_line, word)).strip()
            if len(new_line) >= max_columns:
                break
            words_left = words_left[1:]
            current_line = new_line
        high = len(words) - len(words_left)
        lines.append((low, high))
    return lines
