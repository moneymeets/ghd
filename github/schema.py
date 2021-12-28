from dataclasses import dataclass
from typing import Optional

from dataclasses_json import Undefined, dataclass_json

from .util import DeploymentState


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class Actor:
    login: str


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class Deployment:
    id: int
    ref: str
    environment: str
    original_environment: str
    description: str
    created_at: str
    task: str
    creator: Actor
    transient_environment: Optional[bool]
    production_environment: Optional[bool]


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class DeploymentStatus:
    id: int
    state: DeploymentState
    created_at: str
    description: str
    creator: Actor


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class GitActor:
    name: str
    email: str
    date: str


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class CommitDetails:
    committer: Optional[GitActor]
    author: Optional[GitActor]
    message: str


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class CommitParent:
    sha: str
    url: str
    html_url: str


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class Commit:
    sha: str
    commit: CommitDetails
    committer: Optional[Actor]
    author: Optional[Actor]
    parents: list[CommitParent]


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class Repository:
    private: bool
    full_name: str
