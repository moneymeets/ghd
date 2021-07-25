import os
from typing import Any, Optional, Sequence
import github
import github.GithubObject
import github.Deployment
import github.DeploymentStatus
import github.Commit
import github.Repository

from util import Error
from .util import DeploymentState


class ConstraintError(Error):
    pass


class GithubError(Error):
    @classmethod
    def raise_from_message(cls, payload: dict):
        if not isinstance(payload, dict):
            return
        if message := payload.get("message"):
            raise cls(message)


class GitHub:
    def __init__(self, repo_path: str):
        self._api = github.Github(
            login_or_token=os.environ["GITHUB_TOKEN"],
            user_agent="ghd",
        )
        self.repo_path = repo_path

    @property
    def repo_path(self):
        return self._repo_path

    @repo_path.setter
    def repo_path(self, repo_path: str):
        self._repo = self._api.get_repo(repo_path)
        self._repo_path = repo_path

    def get_deployments(self, environment: Optional[str]) -> Sequence[github.Deployment.Deployment]:
        return tuple(
            self._repo.get_deployments(
                environment=environment if environment else github.GithubObject.NotSet,
            ),
        )

    def get_recent_deployment(self, environment: Optional[str]) -> Optional[github.Deployment.Deployment]:
        deployments = self.get_deployments(environment)
        return deployments[0] if deployments else None

    def verify_ref_is_deployed_in_previous_environment(
        self,
        sha: str,
        environment: str,
        ordered_environments: Sequence[str],
    ):
        index = ordered_environments.index(environment)
        if index == 0:
            return

        previous_environment = ordered_environments[index - 1]
        if not self.is_successfully_deployed_in_environment(sha, previous_environment):
            raise ConstraintError(
                f"Deployment of {sha} to {environment} failed,"
                f" because a successful deployment to {previous_environment} is missing",
            )

    def is_successfully_deployed_in_environment(self, ref: str, environment: str) -> bool:
        return any(
            (
                (statuses := self.get_deployment_statuses(deployment.id))
                and statuses[0].state == DeploymentState.success.value
            )
            for deployment in self.get_deployments(environment)
            if ref == deployment.sha
        )

    def get_deployment_statuses(self, deployment_id: int) -> Sequence[github.DeploymentStatus.DeploymentStatus]:
        return tuple(self._repo.get_deployment(deployment_id).get_statuses())[::-1]

    def get_commits(self) -> Sequence[github.Commit.Commit]:
        return tuple(self._repo.get_commits())

    def get_commits_until(self, sha: str, until: str) -> tuple[list[github.Commit.Commit], bool]:
        result = []
        commit_found = False
        for commit in self._repo.get_commits(sha=sha):
            if commit.sha == until:
                commit_found = True
                break
            result.append(commit)
        return result, commit_found

    def create_deployment_status(
        self,
        deployment_id: int,
        state: DeploymentState,
        environment: str,
        description: str,
    ) -> int:
        return (
            self._repo.get_deployment(deployment_id)
            .create_status(
                state=state.name,
                description=description,
                environment=environment,
            )
            .id
        )

    def deploy(
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
        deployment_creation_result = self._repo.create_deployment(
            ref=ref,
            auto_merge=False,
            environment=environment,
            transient_environment=transient,
            production_environment=production,
            task=task,
            description=description,
            required_contexts=required_contexts if required_contexts is not None else github.GithubObject.NotSet,
            payload=payload if payload else github.GithubObject.NotSet,
        )
        return deployment_creation_result.id

    @property
    def repositories(self) -> Sequence[github.Repository.Repository]:
        return tuple(self._api.get_user().get_repos())
