#!/usr/bin/env python3
import argparse

import aiohttp
import asyncio
import os
import colorama
import tabulate
import progressbar
import sys

headers = {
    "Content-Type": "application/vnd.github.ant-man-preview+json",
}

if (bearer_token := os.environ.get("GITHUB_TOKEN")) and not os.environ.get("GITHUB_ACCESS_TOKEN"):
    print("GitHub Workflow detected")
    auth = None
    headers["Authorization"] = "Bearer " + bearer_token
else:
    auth = aiohttp.BasicAuth(login=os.environ["GITHUB_USER"], password=os.environ["GITHUB_ACCESS_TOKEN"])

headers_flash = {
    **headers,
    "Accept": "application/vnd.github.flash-preview+json",
}

headers_ant_man = {
    **headers,
    "Accept": "application/vnd.github.ant-man-preview+json",
}

YES = colorama.Fore.GREEN + colorama.Style.BRIGHT + "yes" + colorama.Fore.RESET + colorama.Style.RESET_ALL
NO = colorama.Fore.RED + "no" + colorama.Fore.RESET
UNKNOWN = colorama.Fore.BLUE + colorama.Style.DIM + "unknown" + colorama.Fore.RESET + colorama.Style.RESET_ALL


class GitHub:
    def __init__(self, repo_path: str):
        assert repo_path

        self.repo_path = repo_path
        self.session_flash = aiohttp.ClientSession(headers=headers_flash, auth=auth)
        self.session_ant_man = aiohttp.ClientSession(headers=headers_ant_man, auth=auth)

        print(f"Working in {repo_path}")

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

    async def create_deployment(self, ref: str, environment: str, transient: bool, production: bool,
                                task: str = "deploy"):
        return await self.post(f'/repos/{self.repo_path}/deployments', {
            "ref": ref,
            "auto_merge": False,
            "environment": environment,
            "transient_environment": transient,
            "production_environment": production,
            "task": task,
            "description": "Deployed from CLI",
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
            tbl["ref"].append(deployment["ref"])
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
                tbl["state"].append(UNKNOWN)
                tbl["status_changed"].append(UNKNOWN)

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

    async def deploy(self, environment: str, ref: str, transient: bool, production: bool):
        print("Creating deployment...")
        tmp = await self.create_deployment(ref=ref,
                                           environment=environment,
                                           transient=transient,
                                           production=production)
        if "id" not in tmp:
            print(tmp)
            raise RuntimeError()

        print(f"::set-output name=deployment_id::{tmp['id']}")
        print(f"Deployment {tmp['id']} created")


def bool_to_str(b):
    if b is None:
        return UNKNOWN
    elif b:
        return YES
    else:
        return NO


def color_state(state: str):
    color = {
        "pending": colorama.Fore.CYAN,
        "queued": colorama.Fore.CYAN,
        "success": colorama.Fore.GREEN,
        "error": colorama.Fore.RED + colorama.Style.BRIGHT,
        "failed": colorama.Fore.RED + colorama.Style.BRIGHT,
        "in_progress": colorama.Fore.YELLOW,
    }.get(state, colorama.Fore.BLUE)

    return color + state + colorama.Fore.RESET + colorama.Style.RESET_ALL


async def main():
    if len(sys.argv) < 2:
        print("Missing action (list, deploy, set-state)")
        exit(1)

    colorama.init()

    use_argv = sys.argv[:]
    cmd = use_argv[1]
    del use_argv[:2]

    epilogue = """
If $GITHUB_TOKEN is present, it is used as the bearer token to authenticate against the API; not that you CANNOT
create deployments using the token provided by GitHub itself in the runner context.

Instead, for deployments, supply a personalized $GITHUB_USER and $GITHUB_ACCESS_TOKEN with all deployment access scopes.
    """

    if cmd == "list":
        argp = argparse.ArgumentParser(description="List deployments", prog="ghd", epilog=epilogue)
        argp.add_argument("-r", "--repo", dest="repo",
                          help="Repository to use, e.g. stohrendorf/ghd; uses $GITHUB_REPOSITORY if present")
        argp.add_argument("-v", "--verbose", dest="verbose", action="store_true", default=False,
                          help="Print deployment states (slow)")
        argp.add_argument("-l", "--limit", dest="limit", type=int, default=10, help="How many deployments to list")
        args = argp.parse_args(use_argv)

        async with GitHub(repo_path=args.repo or os.environ.get("GITHUB_REPOSITORY")) as gh:
            await gh.list(limit=args.limit, verbose=args.verbose)
    elif cmd == "deploy":
        argp = argparse.ArgumentParser(description="Create new deployment", prog="ghd", epilog=epilogue)
        argp.add_argument("-r", "--repo", dest="repo",
                          help="Repository to use, e.g. stohrendorf/ghd; uses $GITHUB_REPOSITORY if present")
        argp.add_argument("-R", "--ref", dest="ref",
                          help="Reference to create the deployment from")
        argp.add_argument("-e", "--environment", dest="environment", required=True,
                          help="Environment name")
        argp.add_argument("-t", "--transient", dest="transient", action="store_true", default=True,
                          help="Mark as transient environment")
        argp.add_argument("-p", "--production", dest="production", action="store_true", default=True,
                          help="Mark as production environment")
        args = argp.parse_args(use_argv)

        async with GitHub(repo_path=args.repo or os.environ.get("GITHUB_REPOSITORY")) as gh:
            await gh.deploy(environment=args.environment, ref=args.ref,
                            transient=args.transient,
                            production=args.production)
    elif cmd == "set-state":
        argp = argparse.ArgumentParser(description="Set deployment state", prog="ghd", epilog=epilogue)
        argp.add_argument("-r", "--repo", dest="repo",
                          help="Repository to use, e.g. stohrendorf/ghd; uses $GITHUB_REPOSITORY if present")
        argp.add_argument("-e", "--environment", dest="environment", required=True,
                          help="Environment name")
        argp.add_argument("-d", "--deployment-id", dest="deployment_id", type=int, required=True,
                          help="Deployment ID")
        argp.add_argument("-s", "--state", dest="state", type=str, required=True,
                          choices=("error", "failure", "pending", "in_progress", "queued", "success"),
                          help="State")
        argp.add_argument("-D", "--description", dest="description", required=False,
                          default="",
                          help="Description")
        args = argp.parse_args(use_argv)

        async with GitHub(repo_path=args.repo or os.environ.get("GITHUB_REPOSITORY")) as gh:
            await gh.create_deployment_status(deployment_id=args.deployment_id,
                                              state=args.state,
                                              environment=args.environment,
                                              description=args.description)
    elif cmd == "inspect":
        argp = argparse.ArgumentParser(description="Inspect deployment state", prog="ghd", epilog=epilogue)
        argp.add_argument("-r", "--repo", dest="repo",
                          help="Repository to use, e.g. stohrendorf/ghd; uses $GITHUB_REPOSITORY if present")
        argp.add_argument("-d", "--deployment-id", dest="deployment_id", type=int, required=True,
                          help="Deployment ID")
        args = argp.parse_args(use_argv)

        async with GitHub(repo_path=args.repo or os.environ.get("GITHUB_REPOSITORY")) as gh:
            await gh.inspect(deployment_id=args.deployment_id)
    else:
        raise RuntimeError(f"Command {cmd} does not exist")


if __name__ == '__main__':
    asyncio.run(main())
