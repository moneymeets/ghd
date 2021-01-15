import json
import os
from typing import Any, Optional, Sequence
from urllib.parse import urlencode

import aiohttp

from util import Error
from .schema import Deployment, DeploymentStatus, Commit, Repository
from .util import DeploymentState


class ConstraintError(Error):
    pass


class GithubError(Error):
    def __init__(self, message: str):
        self.message = message

    @classmethod
    def raise_from_message(cls, payload: dict):
        if not isinstance(payload, dict):
            return
        if message := payload.get("message"):
            raise cls(message)


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

        self.headers_v3 = {
            **headers,
            "Accept": "application/vnd.github.v3+json",
        }

        self.repo_path = repo_path
        self.session_flash = aiohttp.ClientSession(headers=self.headers_flash, auth=auth)
        self.session_ant_man = aiohttp.ClientSession(headers=self.headers_ant_man, auth=auth)
        self.session_v3 = aiohttp.ClientSession(headers=self.headers_v3, auth=auth)

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
        await self.session_v3.close()

    async def get_ant_man(self, path: str):
        async with self.session_ant_man.get(self._api_url(path)) as response:
            return await response.json()

    async def get_flash(self, path: str):
        async with self.session_flash.get(self._api_url(path)) as response:
            return await response.json()

    async def get(self, path: str):
        async with self.session_v3.get(self._api_url(path)) as response:
            return await response.json()

    async def post(self, path: str, json_data: Any):
        async with self.session_ant_man.post(self._api_url(path), json=json_data) as response:
            return await response.json()

    async def post_flash(self, path: str, json_data: Any):
        async with self.session_flash.post(self._api_url(path), json=json_data) as response:
            return await response.json()

    async def get_deployments(self, environment: Optional[str]) -> list[Deployment]:
        try:
            path = f"/repos/{self.repo_path}/deployments"
            if environment:
                environment_param = urlencode({"environment": environment})
                path += f"?{environment_param}"
            return sorted(
                Deployment.schema().load(await self.get_ant_man(path), many=True), key=lambda e: e.id, reverse=True,
            )
        except TypeError:
            return []

    async def get_recent_deployment(self, environment: Optional[str]) -> Optional[Deployment]:
        deployments = await self.get_deployments(environment)
        return deployments[0] if deployments else None

    async def verify_ref_is_deployed_in_previous_environment(
        self, ref: str, environment: str, ordered_environments: Sequence[str],
    ):
        index = ordered_environments.index(environment)
        if index == 0:
            return

        previous_environment = ordered_environments[index - 1]
        if not await self.is_deployed_in_environment(ref, previous_environment):
            raise ConstraintError(
                f"Deployment of {ref} to {environment} failed, because deployment to {previous_environment} is missing",
            )

    async def is_deployed_in_environment(self, ref: str, environment: str) -> bool:
        return any(ref == deployment.ref for deployment in await self.get_deployments(environment))

    async def get_deployment_statuses(self, deployment_id: int) -> list[DeploymentStatus]:
        return sorted(
            DeploymentStatus.schema().load(
                await self.get_ant_man(f"/repos/{self.repo_path}/deployments/{deployment_id}/statuses"), many=True,
            ),
            key=lambda e: e.id,
            reverse=True,
        )

    async def get_commits(self) -> list[Commit]:
        commits = await self.get(f"/repos/{self.repo_path}/commits")
        GithubError.raise_from_message(commits)
        return Commit.schema().load(commits, many=True)

    async def get_commits_until(self, sha: str, until: str) -> tuple[list[Commit], bool]:
        sha_arg = urlencode({"sha": sha})
        commits = await self.get(f"/repos/{self.repo_path}/commits?{sha_arg}")
        GithubError.raise_from_message(commits)
        result = []
        commit_found = False
        for commit in map(Commit.from_dict, commits):
            if commit.sha == until:
                commit_found = True
                break
            result.append(commit)
        return result, commit_found

    async def create_deployment(
        self,
        ref: str,
        environment: str,
        transient: bool,
        production: bool,
        task: str,
        description: str,
        required_contexts: Optional[list[str]],
        payload: Optional[Any] = None,
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
                "payload": json.dumps(payload) if payload else "",
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

    async def deploy(
        self,
        environment: str,
        ref: str,
        transient: bool,
        production: bool,
        task: str,
        description: str,
        required_contexts: Optional[list[str]],
        payload: Optional[Any] = None,
    ) -> int:
        deployment_creation_result = await self.create_deployment(
            ref=ref,
            environment=environment,
            transient=transient,
            production=production,
            task=task,
            description=description,
            required_contexts=required_contexts,
            payload=payload,
        )
        GithubError.raise_from_message(deployment_creation_result)

        if "id" not in deployment_creation_result:
            raise KeyError

        return deployment_creation_result["id"]

    @property
    async def repositories(self) -> list[Repository]:
        result = []
        url = self._api_url("/user/repos")
        while True:
            async with self.session_v3.get(url) as response:
                result += list(map(Repository.from_dict, await response.json()))

                try:
                    url = response.links.getone("next").getone("url")
                except KeyError:
                    return result
