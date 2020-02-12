import re
import subprocess
from functools import wraps
from typing import List, Optional, Tuple

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


def short_sha(ref: str) -> str:
    if re.fullmatch(r"[a-f0-9]{40}", ref):
        return ref[:7]
    else:
        return ref


def get_head_rev() -> Optional[str]:
    exit_code, output = subprocess.getstatusoutput("git rev-parse HEAD")
    return output if exit_code == 0 else None


def get_commit_subject(ref: str) -> Optional[str]:
    exit_code, output = subprocess.getstatusoutput(f"git log --format=%s -n1 {ref}")
    return output if exit_code == 0 else None


def get_repo_from_git():
    exit_code, output = subprocess.getstatusoutput("git remote -v")
    if exit_code != 0:
        return None

    try:
        urls = set([line.split()[1] for line in output.splitlines()])
    except IndexError:
        return None

    unique_urls = set()
    for url in urls:
        # TODO: Use walrus operator when flake8 supports it
        match_git = re.fullmatch(r"git@github\.com:([^/]+/[^/]+)\.git", url)
        if match_git:
            unique_urls.add(match_git.group(1))
        # TODO: Use walrus operator when flake8 supports it
        match_https = re.fullmatch(r"https://github\.com/([^/]+/[^/]+)\.git", url)
        if match_https:
            unique_urls.add(match_https.group(1))

    if len(unique_urls) == 1:
        return next(iter(unique_urls))
    else:
        return None


def deep_dict_get(d: dict, *path):
    current = d
    for key in path:
        if current is None:
            return None
        current = current.get(key)
    return current


def get_repo_fallback(github_event_data):
    return (deep_dict_get(github_event_data, "repository", "full_name")
            or get_repo_from_git())


def bool_to_str(b):
    if b is None:
        return color_unknown("unknown")
    elif b:
        return color_success("yes")
    else:
        return color_error("no")


def parse_require_context(require_context: List[str]) -> Tuple[Optional[List[str]], str]:
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
