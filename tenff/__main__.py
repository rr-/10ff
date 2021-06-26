"""Main executable."""
import argparse
import asyncio

from tenff.game import GameSettings, run_game
from tenff.terminal import TerminalInputHandler
from tenff.util import CORPORA_PATH, get_corpus_path, parse_corpus

DEFAULT_TIME = 60
PROLOG = (
    "A certain typing contest site spin-off in CLI, without all the "
    "advertisements, tracking and 10 megabytes of AJAX crap."
)


class CustomHelpFormatter(argparse.HelpFormatter):
    """A HelpFormatter that uses concise syntax for short and long options
    help.
    """

    def _format_action_invocation(self, action: argparse.Action) -> str:
        """Format action invocation.

        Example of the default argparse formatting:

            -c CORPUS, --corpus CORPUS

        Example of the concise formatting:

            -c, --corpus CORPUS
        """
        if not action.option_strings or action.nargs == 0:
            return super()._format_action_invocation(action)
        default = self._get_default_metavar_for_optional(action)
        args_string = self._format_args(action, default)
        return ", ".join(action.option_strings) + " " + args_string


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="10ff", description=PROLOG, formatter_class=CustomHelpFormatter
    )
    parser.add_argument(
        "-t",
        "--time",
        type=int,
        default=DEFAULT_TIME,
        help="how long to play the game for (in seconds)",
    )
    parser.add_argument(
        "-c",
        "--corpus",
        type=str,
        default="english",
        help="path to the word list to play the game with",
    )
    parser.add_argument(
        "-w",
        "--width",
        type=int,
        default=80,
        help="width of the terminal to play in",
    )
    parser.add_argument(
        "-l", "--list", action="store_true", help="lists the built-in corpora"
    )
    parser.add_argument(
        "-r",
        "--rigorous-spaces",
        action="store_true",
        help="treat double space as an error",
    )
    return parser.parse_args()


def main() -> None:
    """Main program logic. Start the event loop, parse the CLI arguments and
    run the game.
    """
    loop = asyncio.get_event_loop()
    args = parse_args()

    if args.list:
        for path in sorted(CORPORA_PATH.iterdir()):
            if path.suffix == ".txt":
                print(path.stem)
        return

    input_handler = TerminalInputHandler(loop)
    with input_handler.enable_raw_terminal():
        corpus_path = get_corpus_path(args.corpus)
        corpus = parse_corpus(corpus_path)

        settings = GameSettings(
            corpus=corpus,
            max_time=args.time,
            rigorous_spaces=args.rigorous_spaces,
        )

        loop.run_until_complete(
            run_game(
                loop,
                input_handler,
                settings,
            )
        )
        loop.close()


if __name__ == "__main__":
    main()
