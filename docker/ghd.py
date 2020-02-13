#!/usr/bin/env python3
import asyncio
from functools import wraps
from typing import List, Optional

import click
import colorama
from github import DeploymentState, GitHub, get_current_deployment_id, get_current_environment, read_github_event_data
from util import get_head_rev, get_repo_fallback, handle_errors

ORDERED_ENVIRONMENTS = ("dev", "test", "live")


def coroutine(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper


def click_repo_option():
    return click.option("-r", "--repo",
                        envvar="GITHUB_REPOSITORY",
                        required=True,
                        default=get_repo_fallback(read_github_event_data()),
                        help="Repository to use, e.g. moneymeets/ghd")


def click_deployment_id_option():
    deployment_id = get_current_deployment_id()
    return click.option("-d", "--deployment-id",
                        type=int,
                        required=deployment_id is None,
                        default=deployment_id,
                        help="Deployment ID")


@click.group()
def main_group():
    pass


@main_group.command(name="list", short_help="List deployments")
@click_repo_option()
@click.option("-v", "--verbose/--no-verbose",
              required=False,
              default=False,
              help="Print deployment states (slow)")
@click.option("-l", "--limit",
              required=False,
              default=10,
              help="How many deployments to list")
@click.option("-e", "--environment",
              required=False,
              type=click.Choice(choices=ORDERED_ENVIRONMENTS),
              help="Filter by environment")
@coroutine
async def cmd_list(repo: str, verbose: bool, limit: int, environment: Optional[str]):
    async with GitHub(repo_path=repo) as gh:
        await gh.list(limit=limit, verbose=verbose, environment=environment)


@main_group.command(name="deploy", short_help="Create new deployment")
@click_repo_option()
@click.option("-R", "--ref",
              required=True,
              prompt=True,
              envvar="GITHUB_SHA",
              default=lambda: get_head_rev(),
              help="Reference to create the deployment from")
@click.option("-e", "--environment",
              required=True,
              prompt=True,
              type=click.Choice(choices=ORDERED_ENVIRONMENTS),
              help="Environment name")
@click.option("-T", "--task",
              default="deploy",
              help="Deployment task")
@click.option("-t", "--transient/--no-transient",
              required=False,
              prompt=True,
              default=False,
              help="Mark as transient environment")
@click.option("-p", "--production/--no-production",
              required=False,
              prompt=True,
              default=False,
              help="Mark as production environment")
@click.option("-d", "--description",
              default="Deployed via GHD",
              prompt=True,
              help="Deployment description")
@click.option("-c", "--require-context",
              multiple=True,
              default=["+"],
              help="Context required to be in success state for this deployment to run; "
                   "use a single '-' to require no contexts, or a single '+' to require all")
@click.option("-C", "--check-constraints/--no-check-constraints",
              required=False,
              prompt=True,
              default=True,
              help="Check constraints before deployments, e.g. environment restrictions")
@handle_errors
@coroutine
async def cmd_deploy(repo: str, ref: str, environment: str, task: str, transient: bool, production: bool,
                     description: str, require_context: List[str], check_constraints: bool):
    if "-" in require_context:
        if len(require_context) != 1:
            raise RuntimeError("When not requiring any context by using '-', no other contexts must be required")
        require_context = []
    elif "+" in require_context:
        if len(require_context) != 1:
            raise RuntimeError("When requiring all contexts by using '+', no other contexts must be required")
        require_context = None

    async with GitHub(repo_path=repo) as gh:
        if check_constraints:
            await gh.verify_ref_is_deployed_in_previous_environment(ref, environment, ORDERED_ENVIRONMENTS)

        await gh.deploy(environment=environment,
                        ref=ref,
                        transient=transient,
                        production=production,
                        task=task,
                        description=description,
                        required_contexts=require_context)


@main_group.command(name="set-state", short_help="Set deployment state")
@click_repo_option()
@click.option("-e", "--environment",
              required=True,
              default=get_current_environment(),
              type=click.Choice(choices=ORDERED_ENVIRONMENTS),
              help="Environment name")
@click_deployment_id_option()
@click.option("-s", "--state",
              type=click.Choice(choices=DeploymentState.__members__.keys()),
              required=True,
              help="State")
@click.option("-D", "--description",
              default="Deployed via GHD",
              help="Deployment description")
@coroutine
async def cmd_set_state(repo: str, environment: str, deployment_id: int, state: str, description: Optional[str]):
    async with GitHub(repo_path=repo) as gh:
        await gh.create_deployment_status(deployment_id=deployment_id,
                                          state=DeploymentState[state],
                                          environment=environment,
                                          description=description)


@main_group.command(name="inspect", short_help="Inspect deployment state history")
@click_repo_option()
@click.argument("deployment-id",
                type=int,
                required=True,
                nargs=1)
@coroutine
async def cmd_inspect(repo: str, deployment_id: int):
    async with GitHub(repo_path=repo) as gh:
        await gh.inspect(deployment_id=deployment_id)


def run_main():
    colorama.init()
    main_group()


if __name__ == "__main__":
    run_main()
