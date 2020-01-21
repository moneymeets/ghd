import os
import re
import subprocess

from output import color_unknown, color_success, color_error


def short_sha(ref: str) -> str:
    if re.fullmatch(r"[a-f0-9]{40}", ref):
        return ref[:7]
    else:
        return ref


def get_repo_from_git():
    try:
        urls = set([line.split()[1] for line in subprocess.getoutput("git remote -v").splitlines()])
    except IndexError:
        return None

    unique_urls = set()
    for url in urls:
        if matchGit := re.fullmatch(r"git@github\.com:([^/]+/[^/]+)\.git", url):
            unique_urls.add(matchGit.group(1))
        elif matchHttps := re.fullmatch(r"https://github\.com/([^/]+/[^/]+)\.git", url):
            unique_urls.add(matchHttps.group(1))

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


def get_repo_or_fallback(repo: str, github_event_data):
    return (repo
            or os.environ.get("GITHUB_REPOSITORY")
            or deep_dict_get(github_event_data, "repository", "full_name")
            or get_repo_from_git()
            )


def bool_to_str(b):
    if b is None:
        return color_unknown("unknown")
    elif b:
        return color_success("yes")
    else:
        return color_error("no")
