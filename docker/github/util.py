import enum
import json
import os
import re
import subprocess
from typing import Optional

import colorama

from output import color_str, print_info
from util import deep_dict_get


class DeploymentState(enum.Enum):
    error = "error"
    failure = "failure"
    pending = "pending"
    in_progress = "in_progress"
    queued = "queued"
    success = "success"
    inactive = "inactive"


_github_event_data = None


def read_github_event_data():
    global _github_event_data

    if _github_event_data is not None:
        return _github_event_data

    _github_event_data = dict()
    if (github_event_path := os.environ.get("GITHUB_EVENT_PATH")) and os.path.exists(github_event_path):
        print_info("Found GitHub Event Path")
        with open(github_event_path, "r") as f:
            _github_event_data = json.load(f)
    return _github_event_data


def get_current_deployment_id():
    deployment_id = deep_dict_get(read_github_event_data(), "deployment", "id")
    return int(deployment_id) if deployment_id else None


def get_current_environment():
    return deep_dict_get(read_github_event_data(), "deployment", "environment")


def get_state_color(state: DeploymentState):
    return {
        DeploymentState.pending: colorama.Fore.CYAN,
        DeploymentState.queued: colorama.Fore.CYAN,
        DeploymentState.success: colorama.Fore.GREEN,
        DeploymentState.error: colorama.Fore.RED + colorama.Style.BRIGHT,
        DeploymentState.failure: colorama.Fore.RED + colorama.Style.BRIGHT,
        DeploymentState.in_progress: colorama.Fore.YELLOW,
    }.get(state, colorama.Fore.BLUE)


def color_state(state: DeploymentState):
    return color_str(get_state_color(state), state.value)


def short_sha(ref: str, max_length: int = None) -> str:
    if re.fullmatch(r"[a-f0-9]{40}", ref):
        max_length = min(7, max_length or 7)
    return ref[:max_length]


def get_head_rev() -> Optional[str]:
    exit_code, output = subprocess.getstatusoutput("git rev-parse HEAD")
    return output if exit_code == 0 else None


def get_commit_subject(ref: str) -> Optional[str]:
    exit_code, output = subprocess.getstatusoutput(f"git log --format=%s -n1 {ref}")
    return output if exit_code == 0 else None


def get_git_log(base_ref: str, head_ref: str) -> Optional[list[str]]:
    exit_code, output = subprocess.getstatusoutput(
        f"git log '--pretty=format:[%h  %cs  %cn]  %s' '{base_ref}..{head_ref}'",
    )
    return output.splitlines() if exit_code == 0 else None


def get_commit_tags(ref: str) -> list[str]:
    exit_code, output = subprocess.getstatusoutput(f"git describe --tags {ref}")
    return output.splitlines() if exit_code == 0 else []


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
        if match := re.fullmatch(r"git@github\.com:([^/]+/[^/]+)\.git", url):
            unique_urls.add(match.group(1))
        if match := re.fullmatch(r"https://github\.com/([^/]+/[^/]+)\.git", url):
            unique_urls.add(match.group(1))

    if len(unique_urls) == 1:
        return next(iter(unique_urls))
    else:
        return None


def get_repo_fallback(github_event_data):
    return deep_dict_get(github_event_data, "repository", "full_name") or get_repo_from_git()
