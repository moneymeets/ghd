from functools import wraps
from typing import Optional

import click

from output import color_error, color_success, color_unknown, print_error


class Error(Exception):
    exit_code = 1


def handle_errors(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Error as error:
            print_error(str(error))
            exit(error.exit_code)

    return wrapped


def deep_dict_get(d: dict, *path):
    current = d
    for key in path:
        if current is None:
            return None
        current = current.get(key)
    return current


def bool_to_str(b):
    if b is None:
        return color_unknown("unknown")
    elif b:
        return color_success("yes")
    else:
        return color_error("no")


def parse_require_context(require_context: list[str]) -> tuple[Optional[list[str]], str]:
    if "-" in require_context:
        if len(require_context) != 1:
            raise RuntimeError("When not requiring any context by using '-', no other contexts must be required")
        return [], color_error("none")
    elif "+" in require_context:
        if len(require_context) != 1:
            raise RuntimeError("When requiring all contexts by using '+', no other contexts must be required")
        return None, color_success("all")
    else:
        return require_context, color_unknown(", ".join(require_context))


class DependentOptionDefault(click.Option):
    _value_key = "_default_val"

    def __init__(self, *args, depends_on: str, **kwargs):
        self.depends_on = depends_on
        super(DependentOptionDefault, self).__init__(*args, **kwargs)

    def get_default(self, ctx):
        if not hasattr(self, self._value_key):
            arg = ctx.params[self.depends_on]
            default = self.type_cast_value(ctx, self.default(arg))
            setattr(self, self._value_key, default)
        return getattr(self, self._value_key)

    def prompt_for_value(self, ctx):
        default = self.get_default(ctx)

        # only prompt if the default value is None
        if default is None:
            return super(DependentOptionDefault, self).prompt_for_value(ctx)

        return default
