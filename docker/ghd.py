#!/usr/bin/env python3
import asyncio
import os
from functools import wraps

import click
import colorama
from github import DeploymentState, GitHub, get_current_deployment_id, get_current_environment, read_github_event_data
from util import get_repo_fallback


def coroutine(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper


def click_repo_option():
    repo_path = get_repo_fallback(read_github_event_data())
    return click.option("-r", "--repo",
                        required=repo_path is None,
                        default=repo_path,
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
@click.option("-v", "--verbose",
              required=False,
              is_flag=True,
              flag_value=True,
              default=False,
              help="Print deployment states (slow)")
@click.option("-l", "--limit",
              required=False,
              default=10,
              help="How many deployments to list")
@coroutine
async def cmd_list(repo: str, verbose: bool, limit: int):
    async with GitHub(repo_path=repo) as gh:
        await gh.list(limit=limit, verbose=verbose)


@main_group.command(name="deploy", short_help="Create new deployment")
@click_repo_option()
@click.option("-R", "--ref",
              required=True,
              help="Reference to create the deployment from")
@click.option("-e", "--environment",
              required=True,
              prompt=True,
              help="Environment name")
@click.option("-T", "--task",
              default="deploy",
              help="Deployment task")
@click.option("-t", "--transient",
              required=False,
              is_flag=True,
              flag_value=True,
              prompt=True,
              default=False,
              help="Mark as transient environment")
@click.option("-p", "--production",
              required=False,
              is_flag=True,
              flag_value=True,
              prompt=True,
              default=False,
              help="Mark as production environment")
@click.option("-d", "--description",
              default="Deployed via GHD",
              prompt=True,
              help="Deployment description")
@coroutine
async def cmd_deploy(repo: str, ref: str, environment: str, task: str, transient: bool, production: bool,
                     description: str):
    async with GitHub(repo_path=repo) as gh:
        await gh.deploy(environment=environment,
                        ref=ref or os.environ.get("GITHUB_SHA"),
                        transient=transient,
                        production=production,
                        task=task,
                        description=description)


@main_group.command(name="set-state", short_help="Set deployment state")
@click_repo_option()
@click.option("-e", "--environment",
              required=True,
              default=get_current_environment(),
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
async def cmd_set_state(repo: str, environment: str, deployment_id: int, state: str, description: str):
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
