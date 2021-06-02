import asyncio
import concurrent.futures
import curses
import enum
import signal
from dataclasses import dataclass
from typing import Optional

import blessed
import blessed.keyboard
import blessed.sequences
import colorama
from dataclasses_json import dataclass_json
import tabulate

from github import GitHub, GithubError, ConstraintError
from github.schema import Commit, Deployment, DeploymentStatus, Repository
from github.util import get_state_color, short_sha, DeploymentState
from output import color_success, color_error
from saint import ExitApp
from saint.messagebox import MessageBox
from saint.multiview import MultiView
from saint.popover import popover, popover_confirm
from saint.statusbar import StatusBar
from saint.table import Column, Table, TableT
from saint.timer import Timer
from saint.util import exit_app, bullet_join
from saint.widget import Widget
from .utils import localize_date, ORDERED_ENVIRONMENTS, PRODUCTION_ENVIRONMENTS, get_next_environment


class ViewMode(enum.Enum):
    DEPLOYMENTS = enum.auto()
    REPOS = enum.auto()
    ENVIRONMENTS = enum.auto()
    COMMITS = enum.auto()
    PROMOTE = enum.auto()
    DEPLOY = enum.auto()


class DeploymentType(enum.Enum):
    INITIAL = "initial"
    REDEPLOY = "redeploy"
    ROLLBACK = "rollback"
    FORWARD = "forward"
    UNDEFINED = "undefined"


@dataclass_json
@dataclass
class DeploymentPayload:
    type: str  # cannot use "DeploymentType" directly here because it doesn't work with json.dumps
    from_ref: str
    to_ref: str


def bool_to_str(b: Optional[bool], max_length: int):
    if b is None:
        return colorama.Fore.BLUE + "?"[:max_length]
    elif b:
        return colorama.Fore.GREEN + "yes"[:max_length]
    else:
        return colorama.Fore.RED + "no"[:max_length]


def color_state(state: DeploymentState, max_length: int):
    return get_state_color(state) + state.value[:max_length]


class SelectionTable(Table[TableT]):
    on_item_selected: Widget.Signal
    on_item_selection_canceled: Widget.Signal

    def __init__(self, parent: Widget, *columns: Column):
        super().__init__(parent, *columns)
        self.on[curses.KEY_ENTER] += self.on_item_selected
        self.on[curses.KEY_EXIT] += self.on_item_selection_canceled
        self.on["q"] += self.on_item_selection_canceled


class EnvironmentsList(SelectionTable):
    columns = (Column("Environment", Column.getter("name")),)

    @property
    def current_filter(self):
        return self.selected_data["value"]

    def __init__(self, parent: Widget):
        super().__init__(parent)


class RepositoryList(SelectionTable[Repository]):
    columns = (
        Column("Private", lambda row, max_length: bool_to_str(row.private, max_length)),
        Column("Name", lambda row, max_length: row.full_name[:max_length]),
    )

    @property
    def current_repo(self):
        return self.selected_data.full_name

    def __init__(self, parent: Widget):
        super().__init__(parent)


class CommitSelection(SelectionTable[Commit]):
    def _commit_column(self, row: Commit, max_length: int) -> str:
        text = short_sha(row.sha, max_length)
        if envs := [deployment.environment for deployment in self._deployments.data if deployment.ref == row.sha]:
            # display in expected order of environments (i.e., re-orders "test, dev, live" to "dev, test, live")
            envs = [ordered for ordered in ORDERED_ENVIRONMENTS if ordered in envs]
            text = color_success(f"{text} ({', '.join(envs)})")
        return text

    def __init__(self, parent: Widget, deployments: Table[Deployment]):
        self._deployments = deployments

        super().__init__(
            parent,
            Column("Ref", self._commit_column),
            Column("Created", lambda row, max_length: localize_date(row.commit.author.date, max_length)),
            Column("Author", lambda row, max_length: row.author.login[:max_length]),
            Column("Message", lambda row, max_length: row.commit.message.splitlines()[0][:max_length]),
        )


class DeploymentsView(Widget):
    deployments_table: Table[Deployment]
    statuses_table: Table[DeploymentStatus]

    def __init__(self, parent: Widget):
        super().__init__(parent, False)

        self.deployments_table = Table(
            self,
            Column("Created", lambda row, max_length: localize_date(row.created_at, max_length)),
            Column("Creator", lambda row, max_length: row.creator.login[:max_length]),
            Column("Env", lambda row, max_length: row.environment[:max_length]),
            Column("Trans", lambda row, max_length: bool_to_str(row.transient_environment, max_length)),
            Column("Prod", lambda row, max_length: bool_to_str(row.production_environment, max_length)),
            Column("Ref", lambda row, max_length: self._ref_styler(row.ref, max_length)),
            Column("Task", lambda row, max_length: row.task[:max_length]),
            Column("Description", lambda row, max_length: row.description[:max_length]),
        )
        self.deployments_table.flex = 2

        self.statuses_table = Table(
            self,
            Column("Created", lambda row, max_length: localize_date(row.created_at, max_length)),
            Column("Creator", lambda row, max_length: row.creator.login[:max_length]),
            Column("State", lambda row, max_length: color_state(row.state, max_length)),
            Column("Description", lambda row, max_length: row.description[:max_length]),
        )

        # neither "\t" nor ord("\t") work because - thanks to blessed - they're overwritten :/
        # noinspection PyUnresolvedReferences
        self.on[blessed.keyboard.KEY_TAB] += self.focus_next_slot
        self.on[curses.KEY_BTAB] += self.focus_prev_slot

    @property
    def _selected_ref(self) -> Optional[str]:
        data = self.deployments_table.selected_data
        if not data:
            return None
        return data.ref

    def _ref_styler(self, ref: str, max_length: int):
        highlight = colorama.Back.YELLOW + colorama.Fore.BLACK
        return (highlight if ref == self._selected_ref else "") + short_sha(ref, max_length)


class YesNoMessageBox(MessageBox):
    def __init__(self, parent_or_term: Widget):
        super().__init__(parent_or_term, "", (("Yes", True), ("No", False)))


class MainView(MultiView[ViewMode]):
    on_status_changed: Widget.Signal

    def __init__(self, parent: Widget, gh: GitHub):
        super().__init__(parent)
        self._gh = gh

        self._env_list = EnvironmentsList(self)
        self._env_list.on_item_selected += self.apply_environment_selection
        self._env_list.on_item_selection_canceled += self.show_deployments
        self.add(ViewMode.ENVIRONMENTS, self._env_list)

        self._repo_list = RepositoryList(self)
        self._repo_list.on_item_selected += self.apply_repo_selection
        self._repo_list.on_item_selection_canceled += self.cancel_repo_selection
        self.add(ViewMode.REPOS, self._repo_list)

        self._deployments_view = DeploymentsView(self)
        self._deployments_view.on["d"] += self.show_commits
        self._deployments_view.on["e"] += self.select_environment
        self._deployments_view.on["p"] += self.show_promote_confirmation
        self._deployments_view.on["q"] += exit_app
        self._deployments_view.on["r"] += self.reload_deployments
        self._deployments_view.on["s"] += self.show_repo_selection
        self._deployments_view.deployments_table.on_selection_changed += self.deployment_selection_changed
        self.add(ViewMode.DEPLOYMENTS, self._deployments_view)

        self._commits = CommitSelection(self, self._deployments_view.deployments_table)
        self._commits.on["q"] += self.show_deployments
        self._commits.on["r"] += self.reload_commits
        self._commits.on[curses.KEY_ENTER] += self.show_deploy_confirmation
        self.add(ViewMode.COMMITS, self._commits)

        self._promote_view = YesNoMessageBox(self)
        self._promote_view.on_abort += self.show_deployments
        self._promote_view.on_select += self.do_promote
        self.add(ViewMode.PROMOTE, self._promote_view)

        self._deploy_view = YesNoMessageBox(self)
        self._deploy_view.on_abort += self.show_commits
        self._deploy_view.on_select += self.do_deploy
        self.add(ViewMode.DEPLOY, self._deploy_view)

        self._watch_timer = Timer(5, self.refresh_statuses)

        self._cached_statuses = dict()

        self.on["w"] += self._toggle_watch

        self.on_view_switched += self._view_switched

        self._deployment_payload: Optional[DeploymentPayload] = None

    async def _view_switched(self, view):
        select_abort = bullet_join("[enter] select", "[q] abort")

        text = {
            ViewMode.COMMITS: bullet_join("[enter] select", "[q] abort", "[r]eload"),
            ViewMode.DEPLOY: select_abort,
            ViewMode.DEPLOYMENTS: bullet_join(
                "[d]eploy", "[p]romote", "[e]nv filter", "[r]eload", "[s]witch repo", "[w]atch", "[q]uit",
            ),
            ViewMode.ENVIRONMENTS: select_abort,
            ViewMode.PROMOTE: select_abort,
            ViewMode.REPOS: select_abort,
        }[view.current_view]

        await self.on_status_changed(text)

        if view.current_view != ViewMode.DEPLOYMENTS:
            self._watch_timer.stop()

    async def init(self):
        self._fill_environments()
        if self._gh.repo_path:
            await self._reload_deployment_data()
            self.update_environments_table()
            await self.show(ViewMode.DEPLOYMENTS)
        else:
            await self.show_repo_selection(
                self._repo_list, blessed.keyboard.Keystroke(),
            )
            await self.show(ViewMode.REPOS)
        await self.on_view_switched(self)

    async def _toggle_watch(self, widget: Widget, key: blessed.keyboard.Keystroke):
        if self.current_view != ViewMode.DEPLOYMENTS:
            return

        if self._watch_timer.stopped:
            self._watch_timer.start()
        else:
            self._watch_timer.stop()

    async def _reload_deployment_data(self):
        popover(self, "Loading")

        self._cached_statuses = dict()
        self._deployments_view.statuses_table.data = []
        self._deployments_view.deployments_table.data = await self._gh.get_deployments(
            environment=self._env_list.current_filter,
        )
        self.on_paint()
        await self._deployments_view.deployments_table.on_selection_changed(self._deployments_view.deployments_table)

    async def apply_environment_selection(
        self, table: Table, key: blessed.keyboard.Keystroke,
    ):
        await self.show(ViewMode.DEPLOYMENTS)
        await self._reload_deployment_data()

    async def show_deployments(
        self, table: Table, key: blessed.keyboard.Keystroke,
    ):
        await self.show(ViewMode.DEPLOYMENTS)
        return True

    async def apply_repo_selection(self, table: Table, key: blessed.keyboard.Keystroke) -> bool:
        await self.show(ViewMode.DEPLOYMENTS)
        self._gh.repo_path = self._repo_list.current_repo
        await self._env_list.set_selected_index(0)
        await self._reload_deployment_data()
        self.update_environments_table()
        await self._deployments_view.deployments_table.set_selected_index(0)
        return True

    async def cancel_repo_selection(self, widget: Widget, key: blessed.keyboard.Keystroke) -> bool:
        if not self._gh.repo_path:
            raise ExitApp
        await self.show(ViewMode.DEPLOYMENTS)
        return True

    async def select_environment(self, widget: Table, key: blessed.keyboard.Keystroke) -> bool:
        await self.show(ViewMode.ENVIRONMENTS)
        return True

    async def reload_deployments(self, widget: Widget, key: blessed.keyboard.Keystroke) -> bool:
        await self._reload_deployment_data()
        return True

    async def deployment_selection_changed(self, table: Table):
        await self._update_statuses(table, False)

    async def refresh_statuses(self):
        await self._update_statuses(None, True)

    async def _update_statuses(self, table, force: False):
        selected = self._deployments_view.deployments_table.selected_data
        if selected is None:
            self._deployments_view.statuses_table.data = []
            return

        deployment_id = selected.id
        cache_key = (self._gh.repo_path, deployment_id)
        if cache_key in self._cached_statuses and not force:
            data = self._cached_statuses[cache_key]
        else:
            popover(self._deployments_view.statuses_table, "Loading")
            data = self._cached_statuses[cache_key] = await self._gh.get_deployment_statuses(deployment_id)
        self._deployments_view.statuses_table.data = data
        if force:
            self._deployments_view.statuses_table.on_paint()

    async def show_repo_selection(self, widget: Widget, key: blessed.keyboard.Keystroke) -> bool:
        await self.show(ViewMode.REPOS)
        popover(self, "Loading repository list")
        self._repo_list.data = await self._gh.repositories
        return True

    async def _try_or_force_deploy(self, callback):
        try:
            await callback(None)
        except (GithubError, ConstraintError) as ex:
            key = popover_confirm(
                self,
                color_error(
                    f"Failed to create deployment\n\n"
                    f"{ex.message}"
                    f"\n\n(press shift+Y to force deployment, any other key to abort)",
                ),
            )
            if key == "Y":
                try:
                    await callback([])
                except (GithubError, ConstraintError) as ex:
                    popover_confirm(
                        self,
                        color_error(
                            f"Failed to force-create deployment\n\n{ex.message}\n\n(press any key to continue)",
                        ),
                    )
                else:
                    popover_confirm(
                        self, color_success("Deployment forcefully created\n\n(press any key to continue)"),
                    )
        except Exception as ex:
            popover_confirm(
                self,
                color_error(
                    f"An unhandled error occured."
                    f" Please report this at https://github.com/moneymeets/ghd/issues.\n\n"
                    f"{ex}\n\n"
                    f"(press any key to continue)",
                ),
            )

    async def do_promote(self, widget: Widget, key: blessed.keyboard.Keystroke) -> bool:
        _, value = self._promote_view.choice
        if not value:
            await self.show(ViewMode.DEPLOYMENTS)
            return True

        deployment: Deployment = self._deployments_view.deployments_table.selected_data
        next_env = get_next_environment(deployment.environment)
        if not next_env:
            return True

        # no need to check if we're already deployed in the previous environment (which is deployment.environment),
        # as we are already promoting from that deployment

        async def deploy(contexts):
            if contexts is None or contexts != []:
                await self._gh.verify_ref_is_deployed_in_previous_environment(
                    ref=deployment.ref,
                    environment=next_env,
                    ordered_environments=ORDERED_ENVIRONMENTS,
                )
            await self._gh.deploy(
                ref=deployment.ref,
                environment=next_env,
                transient=False,
                production=next_env in PRODUCTION_ENVIRONMENTS,
                task=deployment.task,
                description=deployment.description,
                required_contexts=contexts,
                payload={"ghd": self._deployment_payload.to_dict()},
            )
            self._deployment_payload = None

        await self._try_or_force_deploy(deploy)
        await self.show(ViewMode.DEPLOYMENTS)
        await self._reload_deployment_data()
        return True

    async def do_deploy(self, widget: Widget, key: blessed.keyboard.Keystroke) -> bool:
        _, value = self._deploy_view.choice
        if not value:
            await self._switch_to_commits_view()
            return True

        commit: Commit = self._commits.selected_data

        async def deploy(contexts):
            await self._gh.deploy(
                environment=ORDERED_ENVIRONMENTS[0],
                ref=commit.sha,
                transient=False,
                production=ORDERED_ENVIRONMENTS[0] in PRODUCTION_ENVIRONMENTS,
                task="deploy",
                description=commit.commit.message.splitlines()[0],
                required_contexts=contexts,
                payload={"ghd": self._deployment_payload.to_dict()},
            )
            self._deployment_payload = None

        await self._try_or_force_deploy(deploy)
        await self.show(ViewMode.DEPLOYMENTS)
        await self._reload_deployment_data()
        return True

    async def _get_git_log_diff(self, env: str, ref: str) -> tuple[str, DeploymentPayload]:
        recent_deployment = await self._gh.get_recent_deployment(env)

        if not recent_deployment:
            return (
                colorama.Fore.CYAN + "First deployment to this environment" + colorama.Fore.RESET,
                DeploymentPayload(type=DeploymentType.INITIAL.value, from_ref="", to_ref=ref),
            )

        if recent_deployment.ref == ref:
            return (
                colorama.Fore.CYAN + "No changes. This is a re-deployment." + colorama.Fore.RESET,
                DeploymentPayload(type=DeploymentType.REDEPLOY.value, from_ref=ref, to_ref=ref),
            )

        try:
            rollback = False
            commits, deployment_ref_found = await self._gh.get_commits_until(ref, recent_deployment.ref)
            if not deployment_ref_found:
                # assume a possible rollback
                rollback = True
                commits, deployment_ref_found = await self._gh.get_commits_until(recent_deployment.ref, ref)
        except KeyError:
            return (
                colorama.Fore.RED + "The commit was not found in the repository." + colorama.Fore.RESET,
                DeploymentPayload(type=DeploymentType.UNDEFINED.value, from_ref="", to_ref=ref),
            )

        if not deployment_ref_found:
            git_log_lines = [
                colorama.Fore.CYAN + "Commit list suppressed, too many commits to show." + colorama.Fore.RESET,
                colorama.Fore.YELLOW
                + "Due to this, the update type (rollback or roll forward) could not be determined."
                + colorama.Fore.RESET,
                "",
            ]
            return (
                "\n".join(git_log_lines),
                DeploymentPayload(type=DeploymentType.UNDEFINED.value, from_ref=recent_deployment.ref, to_ref=ref),
            )
        else:
            git_log_lines = (
                [
                    colorama.Fore.YELLOW
                    + "This is a rollback! The following commits will be REMOVED!"
                    + colorama.Fore.RESET,
                    "",
                ]
                if rollback
                else []
            )

            def colorize_message(message: str, is_merge_commit: bool):
                return (
                    message
                    if not is_merge_commit
                    else f"{colorama.Fore.GREEN}{colorama.Style.BRIGHT}{message}{self.style.default}"
                )

            table_data = {
                "sha": [],
                "committed": [],
                "author": [],
                "message": [],
            }
            for commit in commits[::-1]:
                table_data["sha"].append(short_sha(commit.sha))
                table_data["committed"].append(localize_date(commit.commit.committer.date))
                table_data["author"].append(commit.author.login)
                message, *_ = commit.commit.message.splitlines()
                table_data["message"].append(colorize_message(message, len(commit.parents) > 1))

            git_log_lines += tabulate.tabulate(table_data, headers="keys").splitlines()

            return (
                "\n".join(git_log_lines),
                DeploymentPayload(
                    type=DeploymentType.ROLLBACK.value if rollback else DeploymentType.FORWARD.value,
                    from_ref=recent_deployment.ref,
                    to_ref=ref,
                ),
            )

    async def show_promote_confirmation(self, widget: Widget, key: blessed.keyboard.Keystroke) -> bool:
        deployment: Optional[Deployment] = self._deployments_view.deployments_table.selected_data
        if deployment is None:
            return True

        next_env = get_next_environment(deployment.environment)
        if not next_env:
            return True

        await self.show(ViewMode.PROMOTE)
        git_log, self._deployment_payload = await self._get_git_log_diff(next_env, deployment.ref)

        self._promote_view.choice_index = 1  # default to "No"
        self._promote_view.message = f"""Promote from {deployment.environment} to {next_env}?

Creator            {deployment.creator.login}
Created            {localize_date(deployment.created_at)}
Ref                {short_sha(deployment.ref)}
Description        {deployment.description}
Task               {deployment.task}
Transient          {bool_to_str(False, 100)}{self.style.default}
Production         {bool_to_str(next_env in PRODUCTION_ENVIRONMENTS, 100)}{self.style.default}
Required Contexts  All
Check constraints  {bool_to_str(True, 100)}{self.style.default}

{git_log}"""

        return True

    async def show_deploy_confirmation(self, widget: Widget, key: blessed.keyboard.Keystroke) -> bool:
        commit: Optional[Commit] = self._commits.selected_data
        if commit is None:
            return True

        await self.show(ViewMode.DEPLOY)
        git_log, self._deployment_payload = await self._get_git_log_diff(ORDERED_ENVIRONMENTS[0], commit.sha)

        self._deploy_view.choice_index = 1  # default to "No"
        self._deploy_view.message = f"""Deploy {short_sha(commit.sha)} to {ORDERED_ENVIRONMENTS[0]}?

Author             {commit.author.login}
Created            {localize_date(commit.commit.committer.date)}
Ref                {short_sha(commit.sha)}
Description        {commit.commit.message.splitlines()[0]}
Transient          {bool_to_str(False, 100)}{self.style.default}
Production         {bool_to_str(ORDERED_ENVIRONMENTS[0] in PRODUCTION_ENVIRONMENTS, 100)}{self.style.default}
Required Contexts  All
Check constraints  {bool_to_str(True, 100)}{self.style.default}

{git_log}"""

        return True

    def _fill_environments(self, *envs: str):
        self._env_list.data = [{"name": "<all>", "value": None}] + [{"name": name, "value": name} for name in envs]

    def update_environments_table(self):
        envs = sorted({row.environment for row in self._deployments_view.deployments_table.data})
        self._fill_environments(*envs)

    async def reload_commits(self, widget: Widget, key: blessed.keyboard.Keystroke) -> bool:
        popover(self, "Loading commits")
        _, widget.data = await asyncio.gather(self._reload_deployment_data(), self._gh.get_commits())
        return True

    async def _switch_to_commits_view(self):
        popover(self, "Loading commits")
        self._commits.data = await self._gh.get_commits()
        await self.show(ViewMode.COMMITS)

    async def show_commits(self, widget: Widget, key: blessed.keyboard.Keystroke) -> bool:
        await self._switch_to_commits_view()
        return True


class MainWindow(StatusBar):
    def __init__(self, term: blessed.Terminal, gh: GitHub):
        super().__init__(term)
        self._main_view = MainView(self, gh)
        self._main_view.on_status_changed += self._change_text
        self.on_resize(term.width, term.height)
        self._resized = False

        def sigwinch_handler():
            self._resized = True

            async def async_handler():
                self.on_paint()

            asyncio.get_event_loop().create_task(async_handler())

        asyncio.get_event_loop().add_signal_handler(signal.SIGWINCH, sigwinch_handler)

    async def _change_text(self, text: str):
        self.text = text

    async def init(self):
        await self._main_view.init()

    def on_paint(self):
        while self._resized:
            self._resized = False
            self.on_resize(self.term.width, self.term.height)
            self.screen.clear()
            super().on_paint()
        else:
            self.screen.clear()
            super().on_paint()

        self.screen.output()


async def gui_main(gh: GitHub):
    try:
        term = blessed.Terminal()

        def get_key():
            with term.raw():
                return term.inkey()

        with term.fullscreen(), term.hidden_cursor():
            main = MainWindow(term, gh)
            await main.init()

            while True:
                main.on_paint()
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    key = await asyncio.get_event_loop().run_in_executor(pool, get_key)
                await main.on_input(key)
    except ExitApp:
        pass
