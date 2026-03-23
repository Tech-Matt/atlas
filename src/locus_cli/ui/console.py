# Rich will read the properties of the console being used and optimize the
# use of colors everywhere when it is used in other parts of the project
import os
from rich.console import Console

console = Console()

_nerd_fonts_warned = False

def supports_unicode() -> bool:
    """Return True if the terminal encoding supports Unicode (UTF-8 etc.)."""
    return console.encoding.lower().startswith("utf")

def supports_nerd_fonts() -> bool:
    """Check if the terminal is likely to support Nerd Fonts, and warn if not explicitly configured."""
    # Since there's no standard way to detect Nerd Fonts, we use common terminal 
    # env vars as heuristics, or rely on a user-defined LOCUS_NERD_FONTS env var.
    global _nerd_fonts_warned
    
    if os.environ.get("LOCUS_NERD_FONTS") == "1":
        return True
    if os.environ.get("LOCUS_NERD_FONTS") == "0":
        return False
        
    # Heuristics for terminals that often have users with Nerd Fonts configured
    term_program = os.environ.get("TERM_PROGRAM", "").lower()
    has_good_term = any([
        "kitty" in term_program,
        "wezterm" in term_program,
        "iterm" in term_program,
        "warp" in term_program,
        "ghostty" in term_program,
        "alacritty" in term_program,
        "WT_SESSION" in os.environ,  # Windows Terminal
    ])
    
    # If it supports unicode but isn't a known "good" term, warn them once
    if supports_unicode():
        if not has_good_term and not _nerd_fonts_warned:
            console.print("[yellow]Warning: Nerd Fonts might not be configured. Set LOCUS_NERD_FONTS=1 to force or LOCUS_NERD_FONTS=0 to disable icons.[/yellow]")
            _nerd_fonts_warned = True
        return True
        
    return False