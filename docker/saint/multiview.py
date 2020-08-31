from typing import Dict, Generic, Optional, TypeVar, Union

import blessed

from .widget import Widget

MultiViewKey = TypeVar("MultiViewKey")


class MultiView(Widget, Generic[MultiViewKey]):
    on_view_switched: Widget.Signal

    def __init__(self, parent_or_term: Union[Optional[Widget], blessed.Terminal]):
        super().__init__(parent_or_term, False)
        self.current_view: Optional[MultiViewKey] = None
        self.views: Dict[MultiViewKey, Widget] = dict()

    def add(self, key: MultiViewKey, widget: Widget):
        self.views[key] = widget

    async def show(self, view: MultiViewKey):
        self.current_view = view
        self.widgets = [self.views[view]]
        self.on_resize(self.width, self.height)
        await self.on_view_switched()
