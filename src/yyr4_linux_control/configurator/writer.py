"""Safe atomic file output for configuration previews.

Never overwrites source files, never writes to directories, uses
atomic rename within the output directory.
"""

import os
import tempfile
from pathlib import Path


def write_preview(
    html_content: str,
    output_path: Path,
    source_path: Path,
    force: bool = False,
) -> Path:
    """Write *html_content* to *output_path* atomically.

    Raises ``FileExistsError`` if *output_path* exists and *force* is
    ``False``.  Raises ``ValueError`` if *output_path* resolves to the
    same file as *source_path*.  The temporary file is created in the
    same directory as *output_path* to ensure rename atomicity.
    """
    output_path = output_path.resolve()
    source_path = source_path.resolve()

    if output_path == source_path:
        raise ValueError("Output path must differ from source config path")

    if output_path.is_dir():
        raise IsADirectoryError(f"Output path is a directory: {output_path}")

    if output_path.exists() and not force:
        raise FileExistsError(
            f"Output file already exists: {output_path}. Use --force to overwrite."
        )

    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to a temporary file in the same directory
    fd, tmp_name = tempfile.mkstemp(
        suffix=".html",
        prefix=".yyr4-preview-",
        dir=str(output_path.parent),
    )
    try:
        os.write(fd, html_content.encode("utf-8"))
        os.fsync(fd)
        os.close(fd)
        fd = -1

        # Set permissions before rename
        os.chmod(tmp_name, 0o644)

        # Atomic rename
        os.replace(tmp_name, str(output_path))
        return output_path

    except BaseException:
        # Clean up on failure
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
