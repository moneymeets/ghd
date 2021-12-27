import colorama

from saint.widget import Widget


class Placeholder(Widget):
    """
    Just a placeholder widget with a really really ugly visual representation nobody would ever write
    to be distinguishable from surrounding widgets.
    """

    def __init__(self, parent_or_term):
        super().__init__(parent_or_term, True)

    def on_paint(self):
        self.clear_viewport()
        for y in range(self.height):
            self.out(0, y, self.get_line_filler(self.width))

    @staticmethod
    def get_line_filler(width) -> str:
        return colorama.Fore.MAGENTA + colorama.Back.CYAN + "{" * width

    @staticmethod
    def get_reference_data(width: int, height: int):
        return Placeholder.get_line_filler(width) * height
