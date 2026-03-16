# Rich will read the properties of the console being used and optimize the
# use of colors everywhere when it is used in other parts of the project
from rich.console import Console
console = Console()


def supports_unicode() -> bool:
    """Return True if the terminal encoding supports Unicode (UTF-8 etc.)."""
    return console.encoding.lower().startswith("utf")