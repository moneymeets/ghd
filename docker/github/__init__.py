import os
import sys
from typing import Any, List, Optional, Sequence
from urllib.parse import urlencode

import aiohttp
import progressbar
import tabulate

from output import color_unknown, print_info, print_success
from util import Error, bool_to_str
from .util import DeploymentState, color_state, short_sha


class ConstraintError(Error):
    pass


class GitHub:
    @staticmethod
    def _api_url(path: str) -> str:
        return f"https://api.github.com{path}"

    def __init__(self, repo_path: str):
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

    def __enter__(self) -> None:
        raise TypeError("Use async with instead")

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # __exit__ should exist in pair with __enter__ but never executed
        pass  # pragma: no cover

    async def __aenter__(self) -> "GitHub":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.session_flash.close()
        await self.session_ant_man.close()

    async def get(self, path: str):
        async with self.session_ant_man.get(self._api_url(path)) as response:
            result = await response.json()
            return result

    async def get_flash(self, path: str):
        async with self.session_flash.get(self._api_url(path)) as response:
            result = await response.json()
            return result

    async def post(self, path: str, json_data: Any):
        async with self.session_ant_man.post(self._api_url(path), json=json_data) as response:
            result = await response.json()
            return result

    async def post_flash(self, path: str, json_data: Any):
        async with self.session_flash.post(self._api_url(path), json=json_data) as response:
            result = await response.json()
            return result

    async def get_deployments(self, environment: Optional[str]) -> list:
        try:
            path = f"/repos/{self.repo_path}/deployments"
            if environment:
                environment_param = urlencode({"environment": environment})
                path += f"?{environment_param}"
            return sorted(await self.get(path), key=lambda e: e["id"], reverse=True)
        except TypeError:
            return []

    async def get_recent_deployment(self, environment: Optional[str]) -> Optional[dict]:
        deployments = await self.get_deployments(environment)
        return deployments[0] if deployments else None

    async def verify_ref_is_deployed_in_previous_environment(
        self, ref: str, environment: str, ordered_environments: Sequence[str],
    ):
        index = ordered_environments.index(environment)
        previous_environment = ordered_environments[index - 1] if index != 0 else None

        if previous_environment is not None and await self.is_deployed_in_environment(ref, previous_environment):
            raise ConstraintError(
                f"Deployment of {ref} to {environment} failed, because deployment to {previous_environment} is missing",
            )

    async def is_deployed_in_environment(self, ref: str, environment: str) -> bool:
        return any(ref == deployment["ref"] for deployment in await self.get_deployments(ref, environment))

    async def get_deployment_statuses(self, deployment_id: int) -> list:
        return sorted(
            await self.get(f"/repos/{self.repo_path}/deployments/{deployment_id}/statuses"),
            key=lambda e: e["id"],
            reverse=True,
        )

    async def get_commits_until(self, sha: str, until: str):
        sha_arg = urlencode({"sha": sha})
        commits = await self.get(f"/repos/{self.repo_path}/commits?{sha_arg}")
        if "message" in commits:
            raise KeyError
        result = []
        end_found = False
        for commit in commits:
            if commit["sha"] == until:
                end_found = True
                break
            result.append(commit)
        return result, end_found

    async def create_deployment(
        self,
        ref: str,
        environment: str,
        transient: bool,
        production: bool,
        task: str,
        description: str,
        required_contexts: Optional[List[str]],
    ):
        return await self.post(
            f"/repos/{self.repo_path}/deployments",
            {
                "ref": ref,
                "auto_merge": False,
                "environment": environment,
                "transient_environment": transient,
                "production_environment": production,
                "task": task,
                "description": description,
                "required_contexts": required_contexts,
            },
        )

    async def create_deployment_status(
        self, deployment_id: int, state: DeploymentState, environment: str, description: str,
    ):
        post_fn = self.post_flash if state != DeploymentState.inactive else self.post

        return await post_fn(
            f"/repos/{self.repo_path}/deployments/{deployment_id}/statuses",
            {"state": state.name, "description": description, "environment": environment},
        )

    async def list(self, limit: int, verbose: bool, environment: Optional[str]):
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

        for deployment in progressbar.progressbar(
            (await self.get_deployments(environment))[:limit],
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

    async def deploy(
        self,
        environment: str,
        ref: str,
        transient: bool,
        production: bool,
        task: str,
        description: str,
        required_contexts: Optional[List[str]],
    ):
        print_info("Creating deployment")
        deployment_creation_result = await self.create_deployment(
            ref=ref,
            environment=environment,
            transient=transient,
            production=production,
            task=task,
            description=description,
            required_contexts=required_contexts,
        )
        if "id" not in deployment_creation_result:
            print(deployment_creation_result)
            raise RuntimeError()

        print(f"::set-output name=deployment_id::{deployment_creation_result['id']}")
        print_success(f"Deployment {deployment_creation_result['id']} created")

    @property
    async def repositories(self):
        result = []
        page = 1
        while True:
            repos = await self.get(f"/user/repos?page={page}")
            if not repos:
                return result
            page += 1
            result += repos
