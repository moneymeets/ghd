import asyncio
from datetime import datetime
from functools import wraps
from typing import Any, Optional, Sequence

import click
from babel.dates import format_datetime

from github import ConstraintError, GitHub
from github.util import get_current_deployment_id, get_repo_fallback, read_github_event_data

PRODUCTION_ENVIRONMENTS = ("live",)
ORDERED_ENVIRONMENTS = ("dev", "test") + PRODUCTION_ENVIRONMENTS


def coroutine(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper


def click_repo_option(required: bool = True):
    return click.option(
        "-r",
        "--repo",
        envvar="GITHUB_REPOSITORY",
        required=required,
        default=get_repo_fallback(read_github_event_data()),
        help="Repository to use, e.g. moneymeets/ghd",
    )


def click_deployment_id_option():
    deployment_id = get_current_deployment_id()
    return click.option(
        "-d",
        "--deployment-id",
        type=int,
        required=deployment_id is None,
        default=deployment_id,
        help="Deployment ID",
    )


def localize_date(date: str, max_length: int = 0):
    result = format_datetime(datetime.strptime(f"{date}+0000", "%Y-%m-%dT%H:%M:%SZ%z").astimezone())
    return result[:max_length] if max_length else result


def get_next_environment(env: str) -> Optional[str]:
    try:
        return ORDERED_ENVIRONMENTS[ORDERED_ENVIRONMENTS.index(env) + 1]
    except (KeyError, IndexError, ValueError):
        # IndexError if we're already in the last environment in the chain
        # ValueError if the environment is not in the deployment chain
        return None


async def deploy(
    gh: GitHub,
    ref: str,
    environment: str,
    task: str,
    transient: bool,
    production: bool,
    description: str,
    check_constraints: bool,
    exclude_check_run_names: Sequence[str],
    exclude_check_run_conclusions: Sequence[str],
    force: bool,
    payload: Optional[Any] = None,
) -> int:
    if not force:
        if check_constraints:
            await gh.verify_ref_is_deployed_in_previous_environment(
                ref,
                environment,
                ORDERED_ENVIRONMENTS,
            )

        check_runs = await gh.get_check_runs(ref)

        # Filter out check runs by names and conclusions
        check_runs = tuple(
            filter(
                lambda run: (run["conclusion"] not in exclude_check_run_conclusions)
                and (run["name"] not in exclude_check_run_names),
                check_runs,
            ),
        )

        # All filtered check runs should be in a success conclusion to deploy the application
        if not all(run["conclusion"] == "success" for run in check_runs):
            raise ConstraintError(
                f"Deployment of {ref} to {environment} failed, because there are some checks not in a success state.",
            )

    return await gh.deploy(
        environment=environment,
        ref=ref,
        transient=transient,
        production=production,
        task=task,
        description=description,
        payload=payload,
    )
