"""The SoftglowOS version for the Settings page and bug reports."""


def version():
    """The SoftglowOS version and the build date of the Hub package, e.g.
    ("1.0.0", "2026-11-08"). Empty outside SoftglowOS (Dev VM)."""
    def read(name):
        try:
            with open(f'/usr/share/softglowos/{name}') as file:
                return file.read().strip()
        except OSError:
            return ''
    return read('version'), read('build-date')
