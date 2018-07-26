#!/usr/bin/env python3
import asyncio
import argparse
import pathlib

from .game import Game

DEFAULT_TIME = 60


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--time', type=int, default=DEFAULT_TIME)
    parser.add_argument(
        '-c', '--corpus',
        type=pathlib.Path,
        dest='corpus_path',
        default=pathlib.Path(__file__).parent / 'data' / 'english.txt'
    )
    parser.add_argument('-w', '--width', type=int, default=80)
    return parser.parse_args()


def main():
    loop = asyncio.get_event_loop()
    args = parse_args()
    game = Game(loop, args)
    loop.run_until_complete(game.run())
    loop.close()


if __name__ == '__main__':
    main()
