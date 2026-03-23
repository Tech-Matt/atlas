"""
LLM inference for `locus overview`.

Uses llama-cpp-python for local inference against a GGUF model.
GPU acceleration is controlled at runtime via n_gpu_layers:
  -1 → offload all layers to GPU
   0 → CPU only
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .extractor import ProjectContext

_SYSTEM_PROMPT = (
    "You are a senior software engineer analysing an unfamiliar codebase. "
    "Write a clear, concise overview report. Be specific and factual. "
    "Focus on: what the project does, its architecture, key components, "
    "and entry points. Maximum 400 words."
)

_GPU_INSTALL_HINTS = {
    "NVIDIA": (
        "pip install llama-cpp-python "
        "--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121"
    ),
    "AMD": (
        "pip install llama-cpp-python "
        "--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/rocm60"
    ),
}


def gpu_install_hint(gpu_type: str) -> str | None:
    """Return the pip install hint for enabling GPU support, or None."""
    return _GPU_INSTALL_HINTS.get(gpu_type.upper())


def warn_if_gpu_unsupported(gpu_type: str, n_gpu_layers: int) -> None:
    """Print a warning to console if GPU was requested but is not supported."""
    if n_gpu_layers != -1:
        return
    if check_gpu_support():
        return
    from ..ui.console import console
    gpu = gpu_type.upper()
    if gpu == "NVIDIA":
        hint = f"  NVIDIA: {_GPU_INSTALL_HINTS.get('NVIDIA', '')}"
    elif gpu == "AMD":
        hint = f"  AMD:    {_GPU_INSTALL_HINTS.get('AMD', '')}"
    else:
        hint = (
            f"  NVIDIA: {_GPU_INSTALL_HINTS.get('NVIDIA', '')}\n"
            f"  AMD:    {_GPU_INSTALL_HINTS.get('AMD', '')}"
        )
    console.print(
        "\n[yellow]Warning: llama-cpp-python was not compiled with GPU support.\n"
        f"Inference will run on CPU. To enable GPU acceleration:\n\n"
        f"{hint}[/yellow]\n"
    )


def check_gpu_support() -> bool:
    """Return True if llama-cpp-python was compiled with GPU offload support."""
    try:
        from llama_cpp import llama_supports_gpu_offload  # type: ignore[import]
        return bool(llama_supports_gpu_offload())
    except Exception:
        # ImportError, AttributeError, OSError (native lib load failure), etc.
        return False


def build_prompt(ctx: ProjectContext) -> str:
    """Build the user-turn prompt from a ProjectContext."""
    parts: list[str] = [
        f"Project type: {ctx.project_type}",
        f"Primary language: {ctx.primary_language}",
    ]
    if ctx.dependency_file:
        parts.append(f"Dependency file: {ctx.dependency_file}")

    parts.append(f"\nDirectory structure:\n{ctx.tree_summary}")

    if ctx.readme:
        parts.append(f"\nREADME (possibly truncated):\n{ctx.readme}")

    for file_path, content in ctx.snippets:
        parts.append(f"\n--- {file_path} ---\n{content}")

    parts.append("\nWrite the overview report now:")
    return "\n".join(parts)


def stream_overview(
    model_path: str | Path,
    ctx: ProjectContext,
    n_gpu_layers: int = 0,
    on_token: Callable[[str], None] | None = None,
) -> str:
    """
    Load the GGUF model and stream a codebase overview.

    Args:
        model_path:    path to the .gguf model file.
        ctx:           ProjectContext built by extractor.extract_context().
        n_gpu_layers:  -1 = full GPU offload, 0 = CPU only.
        on_token:      called with each text token as it is generated.

    Returns:
        The complete generated text.

    Raises:
        ImportError: if llama-cpp-python is not installed.
    """
    try:
        from llama_cpp import Llama  # type: ignore[import]
    except Exception as exc:
        raise ImportError(
            f"Failed to load llama-cpp-python: {exc}\n"
            "Install it with: pip install llama-cpp-python"
        ) from exc

    llm = Llama(
        model_path=str(model_path),
        n_gpu_layers=n_gpu_layers,
        n_ctx=8192,
        verbose=False,
        chat_format="chatml",
    )

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": build_prompt(ctx)},
    ]

    full: list[str] = []
    for chunk in llm.create_chat_completion(
        messages=messages,
        max_tokens=800,
        stream=True,
        temperature=0.3,
    ):
        delta = chunk["choices"][0]["delta"]
        token: str = delta.get("content", "")
        if token:
            full.append(token)
            if on_token:
                on_token(token)

    return "".join(full)
