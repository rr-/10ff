import argparse
import asyncio

from .game import Game
from .util import get_corpus_path

DEFAULT_TIME = 60


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--time", type=int, default=DEFAULT_TIME)
    parser.add_argument("-c", "--corpus", type=str, default="english")
    parser.add_argument("-w", "--width", type=int, default=80)
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
