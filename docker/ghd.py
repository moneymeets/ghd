#!/usr/bin/env python3
import argparse

import aiohttp
import asyncio
import os
import colorama
import tabulate
import progressbar
import sys
import subprocess
import re
import json


def color_str(color, s):
    return f"{color}{s}{colorama.Fore.RESET}{colorama.Style.RESET_ALL}"


def color_print(color, s, **kwargs):
    print(color_str(color, s), **kwargs)


def print_fatal(s, **kwargs):
    color_print(colorama.Fore.RED + colorama.Style.BRIGHT, s, **kwargs)


def color_error(s):
    return color_str(colorama.Fore.RED, s)


def print_error(s, **kwargs):
    print(color_error(s), **kwargs)


def color_warning(s):
    return color_str(colorama.Fore.YELLOW, s)


def print_warning(s, **kwargs):
    print(color_warning(s), **kwargs)


def color_success(s):
    return color_str(colorama.Fore.GREEN, s)


def print_success(s, **kwargs):
    print(color_success(s), **kwargs)


def color_unknown(s):
    return color_str(colorama.Fore.BLUE, s)


def print_unknown(s, **kwargs):
    print(color_unknown(s), **kwargs)


def print_info(s, **kwargs):
    color_print(colorama.Fore.CYAN, s, **kwargs)


def read_github_event_data():
    if (github_event_path := os.environ.get("GITHUB_EVENT_PATH")) and os.path.exists(github_event_path):
        print_info("Found GitHub Event Path")
        with open(github_event_path, "r") as f:
            return json.load(f)
    return dict()


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


class GitHub:
    def __init__(self, repo_path: str):
        assert repo_path

        headers = {
            "Content-Type": "application/vnd.github.ant-man-preview+json",
        }

        if not os.environ.get("GITHUB_USER"):
            auth = None
            headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
        else:
            auth = aiohttp.BasicAuth(login=os.environ["GITHUB_USER"], password=os.environ["GITHUB_TOKEN"])

        self.headers_flash = {
            **headers,
            "Accept": "application/vnd.github.flash-preview+json",
        }

        self.headers_ant_man = {
            **headers,
            "Accept": "application/vnd.github.ant-man-preview+json",
        }

        self.repo_path = repo_path
        self.session_flash = aiohttp.ClientSession(headers=self.headers_flash, auth=auth)
        self.session_ant_man = aiohttp.ClientSession(headers=self.headers_ant_man, auth=auth)

        print_info(f"Working in {repo_path}")

    def __enter__(self) -> None:
        raise TypeError("Use async with instead")

    def __exit__(self,
                 exc_type,
                 exc_val,
                 exc_tb) -> None:
        # __exit__ should exist in pair with __enter__ but never executed
        pass  # pragma: no cover

    async def __aenter__(self) -> 'GitHub':
        return self

    async def __aexit__(self,
                        exc_type,
                        exc_val,
                        exc_tb) -> None:
        await self.session_flash.close()
        await self.session_ant_man.close()

    async def get(self, path: str):
        # print(f"GET {path}")
        async with self.session_ant_man.get(f"https://api.github.com{path}") as response:
            result = await response.json()
            # print(result)
            return result

    async def get_flash(self, path: str):
        # print(f"GET {path}")
        async with self.session_flash.get(f"https://api.github.com{path}") as response:
            result = await response.json()
            # print(result)
            return result

    async def post(self, path: str, json):
        # print(f"POST {path}")
        async with self.session_ant_man.post(f"https://api.github.com{path}", json=json) as response:
            result = await response.json()
            # print(result)
            return result

    async def post_flash(self, path: str, json):
        # print(f"POST {path}")
        async with self.session_flash.post(f"https://api.github.com{path}", json=json) as response:
            result = await response.json()
            # print(result)
            return result

    async def get_deployments(self) -> list:
        try:
            return sorted(await self.get(f'/repos/{self.repo_path}/deployments'), key=lambda e: e["id"], reverse=True)
        except TypeError:
            return []

    async def get_deployment_statuses(self, deployment_id: int) -> list:
        return sorted(await self.get(f'/repos/{self.repo_path}/deployments/{deployment_id}/statuses'),
                      key=lambda e: e["id"],
                      reverse=True)

    async def create_deployment(self, ref: str, environment: str, transient: bool, production: bool, task: str,
                                description: str):
        return await self.post(f'/repos/{self.repo_path}/deployments', {
            "ref": ref,
            "auto_merge": False,
            "environment": environment,
            "transient_environment": transient,
            "production_environment": production,
            "task": task,
            "description": description,
            "required_contexts": [],  # TODO
        })

    async def create_deployment_status(self, deployment_id: int, state: str, environment: str, description: str):
        return await self.post_flash(f'/repos/{self.repo_path}/deployments/{deployment_id}/statuses', {
            "state": state,
            "description": description,
            "environment": environment,
        })

    async def list(self, limit: int, verbose: bool):
        assert limit > 0

        tbl = {
            "id": [],
            "ref": [],
            "task": [],
            "environment": [],
            "creator": [],
            "created": [],
            "status_changed": [],
            "transient": [],
            "production": [],
            "state": [],
            "description": [],
        }

        for deployment in progressbar.progressbar((await self.get_deployments())[:limit], widgets=[
            progressbar.SimpleProgress(),
            " ",
            progressbar.Bar(marker="=", left="[", right="]"),
            " ",
            progressbar.Timer(),
        ], prefix="Getting Deployments ", fd=sys.stdout):
            tbl["ref"].append(short_sha(deployment["ref"]))
            tbl["id"].append(deployment["id"])
            env = deployment["environment"]
            oenv = deployment["original_environment"]

            tbl["environment"].append(env if env == oenv else f"{env} <- {oenv}")
            tbl["creator"].append(deployment["creator"]["login"])
            tbl["transient"].append(bool_to_str(deployment.get("transient_environment")))
            tbl["production"].append(bool_to_str(deployment.get("production_environment")))
            tbl["description"].append(deployment["description"])
            tbl["created"].append(deployment["created_at"])
            tbl["task"].append(deployment["task"])

            if not verbose:
                tbl["state"].append("?")
                tbl["status_changed"].append("?")
                continue

            statuses = await self.get_deployment_statuses(deployment["id"])
            if len(statuses) > 0:
                status = statuses[0]
                tbl["state"].append(color_state(status["state"]))
                tbl["status_changed"].append(status["created_at"])
            else:
                tbl["state"].append(color_unknown("unknown"))
                tbl["status_changed"].append(color_unknown("unknown"))

        print(tabulate.tabulate(tbl, headers="keys"))

    async def inspect(self, deployment_id: int):

        tbl = {
            "state": [],
            "environment": [],
            "creator": [],
            "created": [],
            "description": [],
        }
        for status in await self.get_deployment_statuses(deployment_id):
            tbl["created"].append(status["created_at"])
            tbl["state"].append(color_state(status["state"]))
            tbl["environment"].append(status["environment"])
            tbl["creator"].append(status["creator"]["login"])
            tbl["description"].append(status["description"])

        print(tabulate.tabulate(tbl, headers="keys"))

    async def deploy(self, environment: str, ref: str, transient: bool, production: bool, task: str, description: str):
        print_info("Creating deployment")
        tmp = await self.create_deployment(ref=ref,
                                           environment=environment,
                                           transient=transient,
                                           production=production,
                                           task=task,
                                           description=description)
        if "id" not in tmp:
            print(tmp)
            raise RuntimeError()

        print(f"::set-output name=deployment_id::{tmp['id']}")
        print_success(f"Deployment {tmp['id']} created")


def bool_to_str(b):
    if b is None:
        return color_unknown("unknown")
    elif b:
        return color_success("yes")
    else:
        return color_error("no")


def color_state(state: str):
    color = {
        "pending": colorama.Fore.CYAN,
        "queued": colorama.Fore.CYAN,
        "success": colorama.Fore.GREEN,
        "error": colorama.Fore.RED + colorama.Style.BRIGHT,
        "failure": colorama.Fore.RED + colorama.Style.BRIGHT,
        "in_progress": colorama.Fore.YELLOW,
    }.get(state, colorama.Fore.BLUE)

    return color_str(color, state)


async def main():
    colorama.init()

    if len(sys.argv) < 2:
        print_error("Missing action (list, inspect, deploy, set-state)")
        exit(1)

    github_event_data = read_github_event_data()

    use_argv = sys.argv[:]
    cmd = use_argv[1]
    del use_argv[:2]

    epilogue = """
$GITHUB_TOKEN must always be present, $GITHUB_USER is optional; note that you CANNOT create deployments using the token
provided by GitHub itself in the runner context, i.e. you must provide a real user's account token and the user's
username if you want the "deployments" event to trigger a workflow.

Instead, for deployments, supply a personalized $GITHUB_USER and $GITHUB_TOKEN with all deployment access scopes.
    """

    current_deployment = deep_dict_get(github_event_data, "deployment", "id")
    current_environment = deep_dict_get(github_event_data, "deployment", "environment")

    if cmd == "list":
        argp = argparse.ArgumentParser(description="List deployments", prog="ghd", epilog=epilogue,
                                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        argp.add_argument("-r", "--repo", dest="repo",
                          help="Repository to use, e.g. moneymeets/ghd")
        argp.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False,
                          help="Print deployment states (slow)")
        argp.add_argument("-l", "--limit", dest="limit", type=int, default=10, help="How many deployments to list")
        args = argp.parse_args(use_argv)

        async with GitHub(repo_path=get_repo_or_fallback(args.repo, github_event_data)) as gh:
            await gh.list(limit=args.limit, verbose=args.verbose)
    elif cmd == "deploy":
        argp = argparse.ArgumentParser(description="Create new deployment", prog="ghd", epilog=epilogue,
                                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        argp.add_argument("-r", "--repo", dest="repo",
                          help="Repository to use, e.g. moneymeets/ghd")
        argp.add_argument("-R", "--ref", dest="ref",
                          help="Reference to create the deployment from")
        argp.add_argument("-e", "--environment", dest="environment", required=True,
                          help="Environment name")
        argp.add_argument("-T", "--task", dest="task", default="deploy",
                          help="Deployment task")
        argp.add_argument("-t", "--transient", dest="transient", action="store_true", default=False,
                          help="Mark as transient environment")
        argp.add_argument("-p", "--production", dest="production", action="store_true", default=False,
                          help="Mark as production environment")
        argp.add_argument("-d", "--description", dest="description", required=False, default="Deployed via GHD",
                          help="Deployment description")
        args = argp.parse_args(use_argv)

        async with GitHub(repo_path=get_repo_or_fallback(args.repo, github_event_data)) as gh:
            await gh.deploy(environment=args.environment, ref=args.ref or os.environ.get("GITHUB_SHA"),
                            transient=args.transient,
                            production=args.production,
                            task=args.task,
                            description=args.description)
    elif cmd == "set-state":
        argp = argparse.ArgumentParser(description="Set deployment state", prog="ghd", epilog=epilogue,
                                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        argp.add_argument("-r", "--repo", dest="repo",
                          help="Repository to use, e.g. moneymeets/ghd")
        argp.add_argument("-e", "--environment", dest="environment", required=current_environment is None,
                          default=current_environment, help="Environment name")
        argp.add_argument("-d", "--deployment-id", dest="deployment_id", type=int, required=current_deployment is None,
                          default=int(current_deployment) if current_deployment else None, help="Deployment ID")
        argp.add_argument("-s", "--state", dest="state", type=str, required=True,
                          choices=("error", "failure", "pending", "in_progress", "queued", "success"),
                          help="State")
        argp.add_argument("-D", "--description", dest="description", required=False,
                          default="",
                          help="Description")
        args = argp.parse_args(use_argv)

        async with GitHub(repo_path=get_repo_or_fallback(args.repo, github_event_data)) as gh:
            await gh.create_deployment_status(deployment_id=args.deployment_id,
                                              state=args.state,
                                              environment=args.environment,
                                              description=args.description)
    elif cmd == "inspect":
        argp = argparse.ArgumentParser(description="Inspect deployment state", prog="ghd", epilog=epilogue,
                                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        argp.add_argument("-r", "--repo", dest="repo",
                          help="Repository to use, e.g. moneymeets/ghd")
        argp.add_argument(dest="deployment_id", type=int, nargs="?", help="Deployment ID")
        args = argp.parse_args(use_argv)

        if args.deployment_id is None and current_deployment is None:
            print_error("Missing deployment id")
            return

        async with GitHub(repo_path=get_repo_or_fallback(args.repo, github_event_data)) as gh:
            await gh.inspect(deployment_id=args.deployment_id or int(current_deployment))
    else:
        raise RuntimeError(f"Command {cmd} does not exist")


def run_main():
    asyncio.run(main())


if __name__ == '__main__':
    run_main()
