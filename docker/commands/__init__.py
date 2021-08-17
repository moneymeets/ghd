import sys
from enum import Enum
from typing import Optional

import click
import progressbar
import tabulate

from github import GitHub
from github.util import (
    DeploymentState,
    color_state,
    get_commit_subject,
    get_commit_tags,
    get_current_environment,
    get_git_log,
    get_head_rev,
    short_sha,
)
from output import color_unknown, print_info, print_success
from util import DependentOptionDefault, bool_to_str, handle_errors, parse_require_context

from .gui import gui_main
from .utils import (
    ORDERED_ENVIRONMENTS,
    PRODUCTION_ENVIRONMENTS,
    click_deployment_id_option,
    click_repo_option,
    coroutine,
)


@click.group()
def main_group():
    pass


@main_group.command(name="list", short_help="List deployments")
@click_repo_option()
@click.option(
    "-v",
    "--verbose/--no-verbose",
    required=False,
    default=False,
    help="Print deployment states (slow)",
)
@click.option(
    "-l",
    "--limit",
    required=False,
    default=10,
    help="How many deployments to list",
)
@click.option(
    "-e",
    "--environment",
    required=False,
    type=click.Choice(choices=ORDERED_ENVIRONMENTS),
    help="Filter by environment",
)
@coroutine
async def cmd_list(repo: str, verbose: bool, limit: int, environment: Optional[str]):
    assert limit > 0

    class Columns(Enum):
        id = "id"
        ref = "ref"
        task = "task"
        environment = "environment"
        creator = "creator"
        created = "created"
        status_changed = "status_changed"
        transient = "transient"
        production = "production"
        state = "state"
        description = "description"

    tbl = {column: [] for column in Columns}

    async with GitHub(repo_path=repo) as gh:

        for deployment in progressbar.progressbar(
            (await gh.get_deployments(environment))[:limit],
            widgets=[
                progressbar.SimpleProgress(),
                " ",
                progressbar.Bar(marker="=", left="[", right="]"),
                " ",
                progressbar.Timer(),
            ],
            prefix="Getting Deployments ",
            fd=sys.stdout,
        ):
            tbl[Columns.ref].append(short_sha(deployment.ref))
            tbl[Columns.id].append(deployment.id)
            env = deployment.environment
            original_env = deployment.original_environment

            tbl[Columns.environment].append(env if env == original_env else f"{env} <- {original_env}")
            tbl[Columns.creator].append(deployment.creator.login)
            tbl[Columns.transient].append(bool_to_str(deployment.transient_environment))
            tbl[Columns.production].append(bool_to_str(deployment.production_environment))
            tbl[Columns.description].append(deployment.description)
            tbl[Columns.created].append(deployment.created_at)
            tbl[Columns.task].append(deployment.task)

            if not verbose:
                tbl[Columns.state].append("?")
                tbl[Columns.status_changed].append("?")
                continue

            statuses = await gh.get_deployment_statuses(deployment.id)
            if len(statuses) > 0:
                status = statuses[0]
                tbl[Columns.state].append(color_state(status.state))
                tbl[Columns.status_changed].append(status.created_at)
            else:
                tbl[Columns.state].append(color_unknown("unknown"))
                tbl[Columns.status_changed].append(color_unknown("unknown"))

        print(tabulate.tabulate({key.value: data for key, data in tbl.items()}, headers="keys"))


@main_group.command(name="deploy", short_help="Create new deployment")
@click_repo_option()
@click.option(
    "-R",
    "--ref",
    required=True,
    prompt=True,
    envvar="GITHUB_SHA",
    default=get_head_rev,
    help="Reference to create the deployment from",
)
@click.option(
    "-e",
    "--environment",
    required=True,
    prompt=True,
    default=ORDERED_ENVIRONMENTS[0],
    type=click.Choice(choices=ORDERED_ENVIRONMENTS),
    help="Environment name",
)
@click.option("-T", "--task", default="deploy", help="Deployment task")
@click.option(
    "-t",
    "--transient/--no-transient",
    required=False,
    prompt=True,
    default=False,
    help="Mark as transient environment",
)
@click.option(
    "-p",
    "--production/--no-production",
    cls=DependentOptionDefault,
    depends_on="environment",
    required=False,
    prompt=True,
    default=lambda environment: environment in PRODUCTION_ENVIRONMENTS,
    help="Mark as production environment",
)
@click.option(
    "-d",
    "--description",
    cls=DependentOptionDefault,
    depends_on="ref",
    default=lambda ref: get_commit_subject(ref) or "Deployed via GHD",
    prompt=True,
    help="Deployment description",
)
@click.option(
    "-c",
    "--require-context",
    multiple=True,
    default=["+"],
    help="Context required to be in success state for this deployment to run; "
    "use a single '-' to require no contexts, or a single '+' to require all",
)
@click.option(
    "-C",
    "--check-constraints/--no-check-constraints",
    required=False,
    prompt=True,
    default=True,
    help="Check constraints before deployments, e.g. environment restrictions",
)
@handle_errors
@coroutine
async def cmd_deploy(
    repo: str,
    ref: str,
    environment: str,
    task: str,
    transient: bool,
    production: bool,
    description: str,
    require_context: list[str],
    check_constraints: bool,
):
    require_context, require_context_str = parse_require_context(require_context)

    tags = ", ".join(get_commit_tags(ref))
    if tags:
        tags = f" ({tags})"

    print_info(f"{repo}@{ref}{tags} will be deployed to {environment}")
    print(f"  transient          {bool_to_str(transient)}")
    print(f"  production         {bool_to_str(production)}")
    print(f"  required contexts  {require_context_str}")
    print(f"  description        {description}")

    async with GitHub(repo_path=repo) as gh:
        recent_deployment = await gh.get_recent_deployment(environment)
        recent_deployment_ref = recent_deployment.ref if recent_deployment else None
        git_log = get_git_log(recent_deployment_ref, ref) if recent_deployment_ref else None

    print()
    if git_log is not None:
        print("\n".join(git_log))
    elif recent_deployment_ref == ref:
        print_info("This commit is currently deployed")
    else:
        print_info("First Deployment to this environment, not showing the commit list")

    print()
    if not click.confirm("Start deployment?"):
        return

    print_info("Creating deployment")

    async with GitHub(repo_path=repo) as gh:
        if check_constraints:
            await gh.verify_ref_is_deployed_in_previous_environment(
                ref,
                environment,
                ORDERED_ENVIRONMENTS,
            )

        deployment_id = await gh.deploy(
            environment=environment,
            ref=ref,
            transient=transient,
            production=production,
            task=task,
            description=description,
            required_contexts=require_context,
        )

        print(f"::set-output name=deployment_id::{deployment_id}")
        print_success(f"Deployment {deployment_id} created")


@main_group.command(name="set-state", short_help="Set deployment state")
@click_repo_option()
@click.option(
    "-e",
    "--environment",
    required=True,
    default=get_current_environment(),
    type=click.Choice(choices=ORDERED_ENVIRONMENTS),
    help="Environment name",
)
@click_deployment_id_option()
@click.option(
    "-s",
    "--state",
    type=click.Choice(choices=DeploymentState.__members__.keys()),
    required=True,
    help="State",
)
@click.option(
    "-D",
    "--description",
    default="Deployed via GHD",
    help="Deployment description",
)
@coroutine
async def cmd_set_state(
    repo: str,
    environment: str,
    deployment_id: int,
    state: str,
    description: Optional[str],
):
    async with GitHub(repo_path=repo) as gh:
        await gh.create_deployment_status(
            deployment_id=deployment_id,
            state=DeploymentState[state],
            environment=environment,
            description=description,
        )


@main_group.command(name="inspect", short_help="Inspect deployment state history")
@click_repo_option()
@click.argument("deployment-id", type=int, required=True, nargs=1)
@coroutine
async def cmd_inspect(repo: str, deployment_id: int):
    class Columns(Enum):
        state = "state"
        environment = "environment"
        creator = "creator"
        created = "created"
        description = "description"

    tbl = {column: [] for column in Columns}

    async with GitHub(repo_path=repo) as gh:
        for status in await gh.get_deployment_statuses(deployment_id):
            tbl[Columns.created].append(status.created_at)
            tbl[Columns.state].append(color_state(status.state))
            tbl[Columns.environment].append(status.environment)
            tbl[Columns.creator].append(status.creator.login)
            tbl[Columns.description].append(status.description)

        print(tabulate.tabulate({key.value: data for key, data in tbl.items()}, headers="keys"))


@main_group.command(name="gui", short_help="Start interactive mode")
@click_repo_option(required=False)
@coroutine
async def cmd_gui(repo: Optional[str]):
    async with GitHub(repo_path=repo or "") as gh:
        await gui_main(gh)
