import blessed
import colorama


class Style:
    def __init__(self, term: blessed.Terminal):
        self._term = term
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
        print(self.default, end="", flush=True)

    def clear_screen(self):
        print(self._term.home + self.default + self._term.clear, end="", flush=True)
