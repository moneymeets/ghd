import asyncio
import concurrent.futures
import curses
import enum
from typing import Optional

import blessed
import blessed.keyboard
import blessed.sequences
import colorama

from github import GitHub
from github.util import get_state_color, short_sha
from saint import ExitApp
from saint.multiview import MultiView
from saint.popover import popover
from saint.statusbar import StatusBar
from saint.table import Column, Table
from saint.timer import Timer
from saint.util import breadcrumbs, exit_app
from saint.widget import Widget
from .utils import localize_date


class ViewMode(enum.Enum):
    DEPLOYMENTS = enum.auto()
    REPOS = enum.auto()
    ENVIRONMENTS = enum.auto()


def bool_to_str(b: Optional[bool], max_length: int):
    if b is None:
        return colorama.Fore.BLUE + "?"[:max_length]
    elif b:
        return colorama.Fore.GREEN + "yes"[:max_length]
    else:
        return colorama.Fore.RED + "no"[:max_length]


def color_state(state: str, max_length: int):
    return get_state_color(state) + state[:max_length]


class SelectionTable(Table):
    on_item_selected: Widget.Signal
    on_item_selection_canceled: Widget.Signal

    def __init__(self, parent: Widget):
        super().__init__(parent)
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


class RepositoryList(SelectionTable):
    columns = (
        Column("Private", Column.getter("private", styler=bool_to_str)),
        Column("Name", Column.getter("full_name")),
    )

    @property
    def current_repo(self):
        return self.selected_data["full_name"]

    def __init__(self, parent: Widget):
        super().__init__(parent)
        self._xxx = None


class DeploymentsView(Widget):
    def __init__(self, parent: Widget):
        super().__init__(parent, False)

        self.deployments_table = Table(
            self,
            Column("Created", Column.getter("created_at", styler=localize_date)),
            Column("Creator", Column.getter("creator", "login")),
            Column("Env", Column.getter("environment")),
            Column("Trans", Column.getter("transient_environment", styler=bool_to_str)),
            Column("Prod", Column.getter("production_environment", styler=bool_to_str)),
            Column("Ref", Column.getter("ref", styler=self._ref_styler)),
            Column("Task", Column.getter("task")),
            Column("Description", Column.getter("description")),
        )
        self.deployments_table.flex = 2

        self.statuses_table = Table(
            self,
            Column("Created", Column.getter("created_at", styler=localize_date)),
            Column("Creator", Column.getter("creator", "login")),
            Column("State", Column.getter("state", styler=color_state)),
            Column("Description", Column.getter("description")),
        )

        # neither "\t" nor ord("\t") work because - thanks to blessed - they're overwritten :/
        self.on[blessed.keyboard.KEY_TAB] += self.focus_next_slot
        self.on[curses.KEY_BTAB] += self.focus_prev_slot

    @property
    def _selected_ref(self) -> Optional[str]:
        data = self.deployments_table.selected_data
        if not data:
            return None
        return data["ref"]

    def _ref_styler(self, ref: str, max_length: int):
        highlight = colorama.Back.YELLOW + colorama.Fore.BLACK
        return (highlight if ref == self._selected_ref else "") + short_sha(ref, max_length)


class MainView(MultiView[ViewMode]):
    on_status_changed: Widget.Signal

    def __init__(self, parent: Widget, gh: GitHub):
        super().__init__(parent)
        self._gh = gh

        self._env_list = EnvironmentsList(self)
        self._env_list.on_item_selected += self.apply_environment_selection
        self._env_list.on_item_selection_canceled += self.cancel_environment_selection
        self.add(ViewMode.ENVIRONMENTS, self._env_list)

        self._repo_list = RepositoryList(self)
        self._repo_list.on_item_selected += self.apply_repo_selection
        self._repo_list.on_item_selection_canceled += self.cancel_repo_selection
        self.add(ViewMode.REPOS, self._repo_list)

        self._deployments_view = DeploymentsView(self)
        self._deployments_view.on["e"] += self.select_environment
        self._deployments_view.on["q"] += exit_app
        self._deployments_view.on["r"] += self.reload_deployments
        self._deployments_view.on["s"] += self.show_repo_selection
        self._deployments_view.deployments_table.on_selection_changed += self.deployment_selection_changed
        self.add(ViewMode.DEPLOYMENTS, self._deployments_view)

        self._watch_timer = Timer(5, self.refresh_statuses)

        self._cached_statuses = dict()

        self.on["w"] += self._toggle_watch

    async def init(self):
        self._fill_environments()
        if self._gh.repo_path:
            await self._reload_data()
            self.update_environments_table()
            self.show(ViewMode.DEPLOYMENTS)
        else:
            await self.show_repo_selection(
                self._repo_list, blessed.keyboard.Keystroke(),
            )
            self.show(ViewMode.REPOS)

    async def _toggle_watch(self, widget: Widget, key: blessed.keyboard.Keystroke):
        if self._watch_timer.stopped:
            self._watch_timer.start()
        else:
            self._watch_timer.stop()

    async def _reload_data(self):
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
        self.show(ViewMode.DEPLOYMENTS)
        await self._reload_data()

    async def cancel_environment_selection(
        self, table: Table, key: blessed.keyboard.Keystroke,
    ):
        self.show(ViewMode.DEPLOYMENTS)
        return True

    async def apply_repo_selection(self, table: Table, key: blessed.keyboard.Keystroke) -> bool:
        self.show(ViewMode.DEPLOYMENTS)
        self._gh.repo_path = self._repo_list.current_repo
        await self._env_list.set_selected_index(0)
        await self._reload_data()
        self.update_environments_table()
        await self._deployments_view.deployments_table.set_selected_index(0)
        return True

    async def cancel_repo_selection(self, widget: Widget, key: blessed.keyboard.Keystroke) -> bool:
        if not self._gh.repo_path:
            raise ExitApp
        self.show(ViewMode.DEPLOYMENTS)
        return True

    async def select_environment(self, widget: Table, key: blessed.keyboard.Keystroke) -> bool:
        self.show(ViewMode.ENVIRONMENTS)
        return True

    async def reload_deployments(self, widget: Widget, key: blessed.keyboard.Keystroke) -> bool:
        await self._reload_data()
        return True

    async def deployment_selection_changed(self, table: Table):
        await self._update_statuses(table, False)

    async def refresh_statuses(self):
        await self._update_statuses(None, True)

    async def _update_statuses(self, table, force: False):
        selected = self._deployments_view.deployments_table.selected_data
        if selected is None:
            self._deployments_view.statuses_table.data = []
            await self.on_status_changed(breadcrumbs(self._gh.repo_path, colorama.Fore.RED + "No Deployments"))
            return

        deployment_id = selected["id"]
        await self.on_status_changed(
            breadcrumbs(self._gh.repo_path, f"Deployment {deployment_id}", selected["description"]),
        )
        cache_key = (self._gh.repo_path, deployment_id)
        if cache_key in self._cached_statuses and not force:
            data = self._cached_statuses[cache_key]
        else:
            popover(self._deployments_view.statuses_table, "Loading")
            data = self._cached_statuses[cache_key] = await self._gh.get_deployment_statuses(deployment_id)
        self._deployments_view.statuses_table.data = data
        if force:
            self._deployments_view.statuses_table.on_paint()
            self._deployments_view.statuses_table.flush()

    async def show_repo_selection(self, widget: Widget, key: blessed.keyboard.Keystroke) -> bool:
        self.show(ViewMode.REPOS)
        popover(self, "Loading repository list")
        self._repo_list.data = await self._gh.repositories
        return True

    def _fill_environments(self, *envs: str):
        self._env_list.data = [{"name": "<all>", "value": None}] + [{"name": name, "value": name} for name in envs]

    def update_environments_table(self):
        envs = sorted({row["environment"] for row in self._deployments_view.deployments_table.data})
        self._fill_environments(*envs)


class MainWindow(StatusBar):
    def __init__(self, term: blessed.Terminal, gh: GitHub):
        super().__init__(term)
        self._main_view = MainView(self, gh)
        self._main_view.on_status_changed += self._change_text
        self.on_resize(term.width, term.height)
        self.auto_resize()

    async def _change_text(self, text: str):
        self.text = text

    async def init(self):
        await self._main_view.init()


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
                main.flush()
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    key = await asyncio.get_event_loop().run_in_executor(pool, get_key)
                await main.on_input(key)
    except ExitApp:
        pass
