from __future__ import annotations # allows forward references in type hints
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
import heapq
import os

@dataclass
class LanguageStat:
    """
    Holds stats for a single language/extension.
    """
    extension: str  # e.g. ".py, .c"
    file_count: int = 0
    total_bytes: int = 0

@dataclass
class ProjectHeuristics:
    """
    Layer 2: pattern matched facts about the project's identity.
    All fields default to None/empty - not every project has a test dir, etc.
    """
    project_type: str | None = None       # e.g. "Python Package", "Node Project"
    dependency_file: str | None = None    # e.g. "pyproject.toml", "package.json"
    entry_points: list[str] = field(default_factory=list)
    test_dirs: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)

@dataclass
class InfoResult:
    """
    The top-level result returned by scan().
    """
    root: Path
    total_files: int = 0
    total_dirs: int = 0
    total_bytes: int = 0
    # default_factory below is a Callable. It is a 0 args function that sets the default
    # value of the variable once the class instance is created (it literally calls list())
    # This is to prevent that a single shared class object is created for all class istances
    languages: list[LanguageStat] = field(default_factory=list)
    heuristics: ProjectHeuristics = field(default_factory=ProjectHeuristics)
    # Top 5 files by size: list of (relative_path_str, bytes), sorted descending
    largest_files: list[tuple[str, int]] = field(default_factory=list)


# -------------------------------------------------------------------
# Lookup tables
# Leading underscore (_) signals "private to this module"
#
# PERFORMANCE NOTE: all of these are module-level constants, evaluated
# once at import time. set/dict lookups are O(1) regardless of size,
# so adding hundreds of entries has no measurable impact on scan speed.
# The real bottleneck is always os.walk() (disk I/O).
# -------------------------------------------------------------------

# Maps a well-known root-level filename → human-readable project type.
_PROJECT_TYPE_MARKERS: dict[str, str] = {
    # Python
    "pyproject.toml":       "Python Package",
    "setup.py":             "Python Package (legacy)",
    "requirements.txt":     "Python Project",
    "Pipfile":              "Python Project (Pipenv)",
    # JavaScript / TypeScript
    "package.json":         "Node.js Project",
    "deno.json":            "Deno Project",
    "deno.jsonc":           "Deno Project",
    "bun.lockb":            "Bun Project",
    # Systems languages
    "Cargo.toml":           "Rust Project",
    "go.mod":               "Go Module",
    "CMakeLists.txt":       "C/C++ (CMake)",
    "Makefile":             "C/C++ (Make)",
    "build.zig":            "Zig Project",
    # JVM
    "pom.xml":              "Java (Maven)",
    "build.gradle":         "Java/Kotlin (Gradle)",
    "build.gradle.kts":     "Kotlin (Gradle)",
    "build.sbt":            "Scala (sbt)",
    # Other languages
    "composer.json":        "PHP Project",
    "Gemfile":              "Ruby Project",
    "mix.exs":              "Elixir Project",
    "rebar.config":         "Erlang Project",
    "stack.yaml":           "Haskell (Stack)",
    "cabal.project":        "Haskell (Cabal)",
    "pubspec.yaml":         "Dart / Flutter Project",
    "Project.toml":         "Julia Project",
    "Package.swift":        "Swift Package",
    "Podfile":              "iOS (CocoaPods)",
}

# Common entry-point filenames to detect the "start" of the program.
# These are O(1) checked against each top-level file name.
_ENTRY_POINT_NAMES: set[str] = {
    # Python
    "main.py", "app.py", "__main__.py", "run.py",
    "manage.py",            # Django
    "wsgi.py", "asgi.py",   # WSGI/ASGI servers
    "server.py", "cli.py",
    # JavaScript / TypeScript
    "index.js", "index.ts", "server.js", "server.ts", "app.js", "app.ts",
    # Systems & compiled
    "main.go",
    "main.c", "main.cpp", "main.cc",
    "main.rs",
    # Other
    "main.rb",
    "main.lua",
    "main.zig",
    "main.nim",
    "index.php",
    "Main.java", "Application.java",   # Java conventions
    "Program.cs",                       # C# convention
}

# Common names for test directories.
_TEST_DIR_NAMES: set[str] = {
    "tests", "test", "__tests__", "spec", "specs",
    "e2e", "integration", "unit", "test_suite", "testing",
    "fixtures", "__mocks__", "cypress",
}

# Common CI, tooling, and configuration files/directories.
# These signal a mature or well-configured project.
_CONFIG_FILE_NAMES: set[str] = {
    # Version control & CI
    ".github",                      # GitHub Actions directory
    ".gitlab-ci.yml",
    ".travis.yml",
    ".circleci",                    # CircleCI directory
    "Jenkinsfile",
    "sonar-project.properties",
    "codecov.yml", "codecov.yaml",
    "renovate.json",
    # Containers
    "Dockerfile", ".dockerfile",
    "docker-compose.yml", "docker-compose.yaml",
    ".dockerignore",
    # Code quality / formatting
    ".pre-commit-config.yaml",
    ".editorconfig",
    ".prettierrc", ".prettierrc.json", ".prettierrc.yml", ".prettierrc.js",
    ".eslintrc.json", ".eslintrc.js", ".eslintrc.yml", ".eslintrc.yaml",
    ".eslintignore",
    ".flake8",
    ".mypy.ini", "mypy.ini",
    "pyrightconfig.json",
    ".bandit",
    # Python test / build
    "pytest.ini", "setup.cfg", "tox.ini", "noxfile.py",
    # Env / runtime
    ".env.example", ".nvmrc", ".python-version",
    # Docs
    ".readthedocs.yml", ".readthedocs.yaml",
}

# Maps file extension (lowercase, with dot) → human-readable language name.
# Used by the rendering layer to display "Python" instead of ".py" etc.
# Extensions for the same language point to the same label string.
_EXTENSION_TO_LANGUAGE: dict[str, str] = {
    # Python
    ".py": "Python", ".pyw": "Python", ".pyi": "Python",
    # JavaScript
    ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".jsx": "JavaScript",
    # TypeScript
    ".ts": "TypeScript", ".tsx": "TypeScript",
    # Web
    ".svelte": "Svelte",
    ".vue": "Vue",
    ".html": "HTML", ".htm": "HTML",
    ".css": "CSS",
    ".scss": "Sass/SCSS", ".sass": "Sass/SCSS",
    ".less": "Less",
    # C family
    ".c": "C", ".h": "C",
    ".cpp": "C++", ".cxx": "C++", ".cc": "C++",
    ".hpp": "C++", ".hxx": "C++", ".hh": "C++",
    ".cs": "C#",
    ".cu": "CUDA", ".cuh": "CUDA",
    # JVM
    ".java": "Java",
    ".kt": "Kotlin", ".kts": "Kotlin",
    ".scala": "Scala",
    ".clj": "Clojure", ".cljs": "Clojure", ".cljc": "Clojure",
    # Systems
    ".rs": "Rust",
    ".go": "Go",
    ".zig": "Zig",
    ".nim": "Nim",
    # Scripting
    ".rb": "Ruby",
    ".php": "PHP",
    ".lua": "Lua",
    ".pl": "Perl", ".pm": "Perl",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell", ".fish": "Shell",
    ".ps1": "PowerShell",
    # Functional
    ".hs": "Haskell", ".lhs": "Haskell",
    ".fs": "F#", ".fsi": "F#", ".fsx": "F#",
    ".ml": "OCaml", ".mli": "OCaml",
    ".ex": "Elixir", ".exs": "Elixir",
    ".erl": "Erlang", ".hrl": "Erlang",
    # Data science
    ".r": "R",
    ".jl": "Julia",
    ".ipynb": "Jupyter Notebook",
    # Mobile
    ".swift": "Swift",
    ".dart": "Dart",
    ".m": "Objective-C", ".mm": "Objective-C",
    # Low-level
    ".asm": "Assembly", ".s": "Assembly",
    # Data / config
    ".json": "JSON",
    ".yaml": "YAML", ".yml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".sql": "SQL",
    ".graphql": "GraphQL", ".gql": "GraphQL",
    ".proto": "Protobuf",
    ".tf": "Terraform", ".tfvars": "Terraform",
    ".nix": "Nix",
    ".csv": "CSV",
    ".md": "Markdown", ".mdx": "Markdown",
    ".txt": "Text",
}

# Default folders to skip — mirrors LocusMap.IGNORE_FOLDERS in map.py.
# Defined here so scanner.py is self-contained (no circular import needed).
_DEFAULT_IGNORE: set[str] = {
    "__pycache__", "node_modules", "venv", "myEnv",
    ".git", ".idea", ".vscode", "dist", "build",
    "target", "bin", "obj", "vendor",
    ".venv", "env", ".env",                 # more common Python venv names
    "out", "output", "cache", ".cache",     # generic build output dirs
    "coverage", ".nyc_output",              # test coverage artifacts
    ".tox", ".nox",                         # Python test runners
}


def scan(
    root: Path,
    ignore: list[str] | None = None,
    on_progress: Callable[[InfoResult], None] | None = None,
) -> InfoResult:
    """
    Walk the directory tree from `root` and return an InfoResult.

    Args:
        root:        directory to scan. Must be an existing directory.
        ignore:      extra directory/file name patterns to skip.
        on_progress: optional callback invoked after each directory is processed,
                     receives the partially-populated InfoResult. Used for live
                     progress displays.
    Returns:
        fully populated InfoResult
    """
    if not root.exists() or not root.is_dir():
        raise ValueError(f"{root} is not a valid directory")

    effective_ignore = _DEFAULT_IGNORE | set(ignore or [])
    result = InfoResult(root=root)
    language_index: dict[str, int] = {}
    size_heap: list[tuple[int, str]] = []

    # Iterative DFS via explicit stack — avoids Python recursion limits on deep trees.
    # Each item is (directory_path, is_root).
    stack: list[tuple[Path, bool]] = [(root, True)]

    while stack:
        current, is_root = stack.pop()

        try:
            entries = list(os.scandir(current))
        except PermissionError:
            continue

        subdirs: list[os.DirEntry[str]] = []

        for entry in entries:
            try:
                # is_dir / is_symlink / is_file on DirEntry use cached d_type on
                # Linux/macOS — no extra syscall unlike Path.is_symlink() + stat().
                is_dir     = entry.is_dir(follow_symlinks=False)
                is_symlink = entry.is_symlink()
                is_file    = entry.is_file(follow_symlinks=False)
            except OSError:
                continue

            if is_dir and not is_symlink:
                if entry.name.startswith("."):
                    # Pruned from traversal, but still check for hidden config dirs (e.g. .github)
                    if is_root and entry.name in _CONFIG_FILE_NAMES:
                        result.heuristics.config_files.append(entry.name)
                    continue
                if entry.name in effective_ignore:
                    continue

                subdirs.append(entry)

                if is_root:
                    if entry.name in _TEST_DIR_NAMES:
                        result.heuristics.test_dirs.append(entry.name)
                    if entry.name in _CONFIG_FILE_NAMES:
                        result.heuristics.config_files.append(entry.name)

            elif is_file and not is_symlink and not entry.name.startswith("."):
                try:
                    size = entry.stat().st_size  # cached on DirEntry after first call
                except OSError:
                    size = 0

                result.total_files += 1
                result.total_bytes += size

                rel_path = str(Path(entry.path).relative_to(root))
                heapq.heappush(size_heap, (size, rel_path))
                if len(size_heap) > 5:
                    heapq.heappop(size_heap)

                ext = Path(entry.name).suffix.lower()
                if ext:
                    if ext in language_index:
                        ls = result.languages[language_index[ext]]
                        ls.file_count += 1
                        ls.total_bytes += size
                    else:
                        ls = LanguageStat(extension=ext, file_count=1, total_bytes=size)
                        language_index[ext] = len(result.languages)
                        result.languages.append(ls)

                if is_root:
                    if result.heuristics.project_type is None and entry.name in _PROJECT_TYPE_MARKERS:
                        result.heuristics.project_type = _PROJECT_TYPE_MARKERS[entry.name]
                        result.heuristics.dependency_file = entry.name
                    if entry.name in _ENTRY_POINT_NAMES:
                        result.heuristics.entry_points.append(entry.name)
                    if entry.name in _CONFIG_FILE_NAMES:
                        result.heuristics.config_files.append(entry.name)

        for d in subdirs:
            result.total_dirs += 1
            stack.append((Path(d.path), False))

        if on_progress:
            on_progress(result)

    result.languages.sort(key=lambda ls: ls.file_count, reverse=True)
    result.languages = result.languages[:5]
    result.largest_files = [(path, size) for size, path in sorted(size_heap, reverse=True)]

    return result