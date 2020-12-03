import blessed
import colorama

from saint.screenbuffer import ScreenBuffer


class Style:
    def __init__(self, term: blessed.Terminal, screen: ScreenBuffer):
        self._term = term
        self._screen = screen

        bg = colorama.Back.BLACK
        fg = colorama.Fore.WHITE
        reset = colorama.Style.RESET_ALL

        self.default = reset + fg + bg
        self.table_header = reset + colorama.Style.BRIGHT + colorama.Fore.WHITE + bg + term.underline
        self.table_row = reset + fg + bg
        self.table_row_selected_focus = reset + colorama.Fore.LIGHTWHITE_EX + colorama.Back.BLUE
        self.table_row_selected = reset + colorama.Fore.LIGHTWHITE_EX + colorama.Back.LIGHTBLACK_EX
        self.status_bar = reset + colorama.Fore.BLACK + colorama.Back.CYAN

    def use_default(self):
        self._screen.print(self.default)

    def clear_screen(self):
        self._screen.print(self._term.home, self.default, self._term.clear)
