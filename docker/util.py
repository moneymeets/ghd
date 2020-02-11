import re
import subprocess
from functools import wraps

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


def get_head_rev():
    exit_code, output = subprocess.getstatusoutput("git rev-parse HEAD")
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
