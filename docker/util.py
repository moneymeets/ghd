import os
import re
import subprocess

from output import color_error, color_success, color_unknown


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
    return (os.environ.get("GITHUB_REPOSITORY")
            or deep_dict_get(github_event_data, "repository", "full_name")
            or get_repo_from_git())


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
