"""Safe atomic file output for configuration previews.

Never overwrites source files, never writes to directories, never
follows output symbolic links, uses atomic rename within the output
directory.
"""

import os
import tempfile
from pathlib import Path


class SameFileError(ValueError):
    """Output path refers to the same file as the source."""


class SymlinkOutputError(ValueError):
    """Output path is a symbolic link — refused for safety."""


def write_preview(
    html_content: str,
    output_path: Path,
    source_path: Path,
    force: bool = False,
) -> Path:
    """Write *html_content* to *output_path* atomically.

    Raises:
        SameFileError: output and source resolve to the same file.
        SymlinkOutputError: output is an existing symbolic link.
        FileExistsError: output exists and *force* is False.
        IsADirectoryError: output is a directory.
        NotADirectoryError: parent of output is not a directory.
        FileNotFoundError: parent of output does not exist.
    """
    # Use abspath (no symlink resolution for the final path)
    output_path = Path(os.path.abspath(str(output_path)))
    source_path = Path(os.path.abspath(str(source_path)))

    # ── Reject symlinks ──
    if output_path.is_symlink():
        raise SymlinkOutputError(
            f"Output path must not be a symbolic link: {output_path}"
        )

    # ── Reject if output refers to source ──
    if _same_file(output_path, source_path):
        raise SameFileError(
            f"Output path must differ from source config path: {output_path}"
        )

    # ── Directory checks ──
    if output_path.is_dir():
        raise IsADirectoryError(f"Output path is a directory: {output_path}")

    parent = output_path.parent
    if not parent.exists():
        raise FileNotFoundError(
            f"Output parent directory does not exist: {parent}"
        )
    if not parent.is_dir():
        raise NotADirectoryError(
            f"Output parent path is not a directory: {parent}"
        )

    # ── Existing file ──
    if output_path.is_file():
        if not force:
            raise FileExistsError(
                f"Output file already exists: {output_path}. "
                f"Use --force to overwrite."
            )

    # ── Atomic write ──
    fd, tmp_name = tempfile.mkstemp(
        suffix=".html",
        prefix=".yyr4-preview-",
        dir=str(parent),
    )
    try:
        os.write(fd, html_content.encode("utf-8"))
        os.fsync(fd)
        os.close(fd)
        fd = -1

        os.chmod(tmp_name, 0o644)
        os.replace(tmp_name, str(output_path))
        return output_path

    except BaseException:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _same_file(a: Path, b: Path) -> bool:
    """Return True if *a* and *b* point to the same file."""
    try:
        return a.stat().st_ino == b.stat().st_ino and a.stat().st_dev == b.stat().st_dev
    except OSError:
        return False
