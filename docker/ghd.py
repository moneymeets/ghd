#!/usr/bin/env python3

import colorama

from commands import main_group


def run_main():
    colorama.init()
    main_group()


if __name__ == "__main__":
    run_main()
