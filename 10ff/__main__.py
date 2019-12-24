import argparse
import asyncio

from .game import Game
from .util import get_corpus_path

DEFAULT_TIME = 60
PROLOG = (
    "A certain typing contest site spin-off in CLI, without all the "
    "advertisements, tracking and 10 megabytes of AJAX crap."
)


class CustomHelpFormatter(argparse.HelpFormatter):
    def _format_action_invocation(self, action):
        if not action.option_strings or action.nargs == 0:
            return super()._format_action_invocation(action)
        default = self._get_default_metavar_for_optional(action)
        args_string = self._format_args(action, default)
        return ", ".join(action.option_strings) + " " + args_string


def parse_args():
    fmt = lambda prog: CustomHelpFormatter(prog)
    parser = argparse.ArgumentParser(
        prog="10ff", description=PROLOG, formatter_class=fmt
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
        help="with of the terminal to play in",
    )
    return parser.parse_args()


def main():
    loop = asyncio.get_event_loop()
    args = parse_args()

    corpus_path = get_corpus_path(args.corpus)

    game = Game(loop, corpus_path, args.time)
    loop.run_until_complete(game.run())
    loop.close()


if __name__ == "__main__":
    main()
