import unittest

from saint.signal import AsyncSignals
from saint.widget import Widget, init_signals


class WidgetMock(Widget):
    on_foo: Widget.Signal

    # noinspection PyMissingConstructor
    def __init__(self):
        # noinspection PyFinal
        self.on = AsyncSignals()


class DerivedWithInit(WidgetMock):
    on_bar: Widget.Signal

    def __init__(self):
        super().__init__()


class DerivedWithoutInit(WidgetMock):
    on_bar: Widget.Signal


class WidgetTest(unittest.TestCase):
    def test_signals_base(self):
        mock = WidgetMock()
        init_signals(mock)
        self.assertTrue(hasattr(mock, "on_foo"))
        self.assertFalse(hasattr(mock, "on_bar"))

    def test_signals_init(self):
        derived = DerivedWithInit()
        init_signals(derived)
        self.assertTrue(hasattr(derived, "on_foo"))
        self.assertTrue(hasattr(derived, "on_bar"))

    def test_signals_no_init(self):
        derived = DerivedWithoutInit()
        init_signals(derived)
        self.assertTrue(hasattr(derived, "on_foo"))
        self.assertTrue(hasattr(derived, "on_bar"))

    def test_signals_no_init_no_init(self):
        class SecondaryWithoutInit(DerivedWithoutInit):
            on_baz: Widget.Signal

        derived = SecondaryWithoutInit()
        init_signals(derived)
        self.assertTrue(hasattr(derived, "on_foo"))
        self.assertTrue(hasattr(derived, "on_bar"))
        self.assertTrue(hasattr(derived, "on_baz"))

    def test_signals_dup_init(self):
        class DerivedDup(WidgetMock):
            on_foo: Widget.Signal

            def __init__(self):
                super().__init__()

        dup = DerivedDup()
        with self.assertRaises(KeyError):
            init_signals(dup)

    def test_signals_dup_no_init(self):
        class DerivedDup(WidgetMock):
            on_foo: Widget.Signal

        dup = DerivedDup()
        with self.assertRaises(KeyError):
            init_signals(dup)

    def test_signals_init_dup_no_init(self):
        class DerivedDupNoInit(DerivedWithInit):
            on_bar: Widget.Signal

        dup_no_init = DerivedDupNoInit()
        with self.assertRaises(KeyError):
            init_signals(dup_no_init)

    def test_signals_init_dup_no_init_init(self):
        class DerivedDupNoInit(DerivedWithInit):
            on_bar: Widget.Signal

        class SecondaryDerivedInit(DerivedDupNoInit):
            on_baz: Widget.Signal

            def __init__(self):
                super().__init__()

        dup = SecondaryDerivedInit()
        with self.assertRaises(KeyError):
            init_signals(dup)
