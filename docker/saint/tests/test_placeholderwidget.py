from unittest import TestCase

import colorama

from saint.tests.placeholderwidget import Placeholder
from saint.tests.virtualterm import VirtualTerm


class TestPlaceholderWidget(TestCase):
    def test_draw_full(self):
        with VirtualTerm(10, 5) as term:
            widget = Placeholder(term.term)
            widget.on_resize(10, 5)
            widget.origin_x, widget.origin_y = (0, 0)
            widget.on_paint()
            widget.screen.output()

            ref_data = term.screen_data

        with VirtualTerm(10, 5) as term:
            term.feed(5 * Placeholder.get_line_filler(10))

            self.assertSequenceEqual(
                ref_data, term.screen_data,
            )

    def test_draw_partial(self):
        with VirtualTerm(10, 5) as term:
            widget = Placeholder(term.term)
            widget.on_resize(10, 2)
            widget.origin_x, widget.origin_y = (0, 2)
            widget.on_paint()
            widget.screen.output()

            ref_data = term.screen_data

        with VirtualTerm(10, 5) as term:
            term.feed(
                colorama.Style.RESET_ALL, colorama.Fore.RESET, colorama.Back.RESET, 2 * " " * 10,
            )
            term.feed(2 * Placeholder.get_line_filler(10))
            term.feed(
                colorama.Style.RESET_ALL, colorama.Fore.RESET, colorama.Back.RESET, 1 * " " * 10,
            )

            self.assertSequenceEqual(
                ref_data, term.screen_data,
            )
