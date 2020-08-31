from dataclasses import dataclass
from typing import Optional

from dataclasses_json import dataclass_json, Undefined

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
    date: str


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class CommitDetails:
    committer: GitActor
    author: GitActor
    message: str


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class Commit:
    sha: str
    commit: CommitDetails
    committer: Actor
    author: Actor


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class Repository:
    private: bool
    full_name: str
