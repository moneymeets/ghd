from typing import NoReturn

from saint import ExitApp


def breadcrumbs(*args) -> str:
    return " \u203a ".join(("",) + args)


async def exit_app(widget, key) -> NoReturn:
    raise ExitApp
