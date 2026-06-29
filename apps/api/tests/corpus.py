"""Corpus path resolver for real-file integration tests.

Walks up from this file until it finds the repo root directory that contains
the `test_files/` corpus, then exposes:

  CORPUS_ROOT  – absolute Path to `test_files/`
  corpus_path("submissions-office-suite/foo.docx")  – absolute path to a corpus file

Import pattern in tests::

    from corpus import corpus_path
    docx_path = corpus_path("submissions-office-suite/PIM_I_FINAL_CORRIGIDO.docx")
"""

from pathlib import Path


def _find_corpus_root() -> Path:
    """Walk up from this file until we find a directory with test_files/."""
    current = Path(__file__).resolve().parent
    for _ in range(10):  # safety limit
        candidate = current / "test_files"
        if candidate.is_dir():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent
    raise FileNotFoundError(
        "Could not locate test_files/ starting from "
        f"{Path(__file__).resolve().parent}. "
        "Make sure the corpus was committed to the repo."
    )


CORPUS_ROOT: Path = _find_corpus_root()


def corpus_path(*parts: str) -> Path:
    """Return the absolute path to a file inside test_files/.

    Example::

        corpus_path("submissions-office-suite/PIM_I_FINAL_CORRIGIDO.docx")
        corpus_path("submissions-code", "greenfit.zip")
    """
    return CORPUS_ROOT.joinpath(*parts)
