import unittest

from saint.statusbar import StatusBar
from saint.tests.placeholderwidget import Placeholder
from saint.tests.virtualterm import VirtualTerm


class StatusbarTest(unittest.TestCase):
    def test_without_widget(self):
        with VirtualTerm(10, 5) as term:
            term.feed("\n" * 4)
            term.feed(term.style.status_bar, "foobar", term.term.clear_eol)

            ref_data = term.screen_data

        with VirtualTerm(10, 5) as term:
            statusbar = StatusBar(term.term)
            statusbar.on_resize(term.width, term.height)
            statusbar.text = "foobar"
            statusbar.on_paint()
            statusbar.flush()

            real_data = term.screen_data

        self.assertSequenceEqual(ref_data, real_data)

    def test_with_widget(self):
        with VirtualTerm(10, 5) as term:
            term.feed(Placeholder.get_reference_data(10, 4))
            term.feed(term.style.status_bar, "foobar", term.term.clear_eol)

            ref_data = term.screen_data

        with VirtualTerm(10, 5) as term:
            statusbar = StatusBar(term.term)
            Placeholder(statusbar)
            statusbar.on_resize(term.width, term.height)
            statusbar.text = "foobar"
            statusbar.on_paint()
            statusbar.flush()

            real_data = term.screen_data

        self.assertSequenceEqual(ref_data, real_data)
