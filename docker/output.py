import colorama


def color_str(color, s):
    return f"{color}{s}{colorama.Fore.RESET}{colorama.Style.RESET_ALL}"


def color_print(color, s, **kwargs):
    print(color_str(color, s), **kwargs)


def print_fatal(s, **kwargs):
    color_print(colorama.Fore.RED + colorama.Style.BRIGHT, s, **kwargs)


def color_error(s):
    return color_str(colorama.Fore.RED, s)


def print_error(s, **kwargs):
    print(color_error(s), **kwargs)


def color_warning(s):
    return color_str(colorama.Fore.YELLOW, s)


def print_warning(s, **kwargs):
    print(color_warning(s), **kwargs)


def color_success(s):
    return color_str(colorama.Fore.GREEN, s)


def print_success(s, **kwargs):
    print(color_success(s), **kwargs)


def color_unknown(s):
    return color_str(colorama.Fore.BLUE, s)


def print_unknown(s, **kwargs):
    print(color_unknown(s), **kwargs)


def print_info(s, **kwargs):
    color_print(colorama.Fore.CYAN, s, **kwargs)
