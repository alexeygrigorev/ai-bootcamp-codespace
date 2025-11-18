import os
import subprocess
from pathlib import Path


class AgentTools:
    def __init__(self, root_dir):
        self.root = Path(root_dir).resolve()
        self.skip_dirs = {
            ".git",
            ".venv",
            "venv",
            "__pycache__",
            ".mypy_cache",
            ".pytest_cache",
            ".idea",
            ".vscode"
        }

    def _safe(self, path):
        p = (self.root / path).resolve()
        if not str(p).startswith(str(self.root)):
            raise ValueError(f"Path escapes root: {p}")
        return p

    def tree(self, path=".", max_depth=None):
        """
        Return only files under `path`, relative to the repo root.
        Skips unwanted directories.
        """
        start = self._safe(path)
        results = []

        def walk(p, depth):
            if max_depth is not None and depth > max_depth:
                return

            for entry in p.iterdir():
                # Skip junk dirs entirely
                if entry.is_dir() and entry.name in self.skip_dirs:
                    continue

                # File? Add it (relative)
                if entry.is_file():
                    rel = entry.relative_to(self.root)
                    results.append(str(rel))

                # Folder? Recurse
                if entry.is_dir():
                    walk(entry, depth + 1)

        walk(start, 0)
        return results

    def grep(self, pattern, path=".", ignore_case=False):
        """Search for files containing pattern. Returns relative paths."""
        search_root = self._safe(path)
        matches = []

        if ignore_case:
            pattern = pattern.lower()

        for root, dirs, files in os.walk(search_root):
            # Remove skipped dirs from traversal
            dirs[:] = [d for d in dirs if d not in self.skip_dirs]

            for file in files:
                file_path = Path(root) / file
                rel = file_path.relative_to(self.root)

                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            hay = line.lower() if ignore_case else line
                            if pattern in hay:
                                matches.append((str(rel), i, line.rstrip()))
                except (OSError, UnicodeDecodeError):
                    continue

        return matches

    def read_file(self, path):
        p = self._safe(path)
        return p.read_text(encoding="utf-8", errors="replace")

    def write_file(self, path, text):
        p = self._safe(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return True

    def execute_bash(self, command, timeout=30):
        """
        Run a bash command inside the repository root, automatically prefixing
        *each* subcommand with 'uv run' unless already present.

        Supports compounds like:
            a && b
            a || b
            a ; b ; c

        Args:
            command (str): Shell command to execute.
            timeout (int): Maximum time before aborting.

        Returns:
            tuple[int, str, str]: (exit_code, stdout, stderr)
        """

        # Operators that separate multiple commands
        separators = ["&&", "||", ";"]

        # Detect which separator is used (simple, but enough for practical use)
        sep_used = None
        for sep in separators:
            if sep in command:
                sep_used = sep
                break

        if sep_used:
            # Split into individual commands
            parts = [c.strip() for c in command.split(sep_used)]

            # Prefix each command with uv run if needed
            processed = []
            for part in parts:
                if part.startswith("uv run "):
                    processed.append(part)
                else:
                    processed.append(f"uv run {part}")

            final_cmd = f" {sep_used} ".join(processed)

        else:
            # Single command
            cmd = command.strip()
            if not cmd.startswith("uv run "):
                cmd = f"uv run {cmd}"
            final_cmd = cmd

        # Execute
        try:
            proc = subprocess.run(
                final_cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=str(self.root),
                timeout=timeout
            )
            return proc.returncode, proc.stdout, proc.stderr

        except subprocess.TimeoutExpired as e:
            return -1, e.stdout or "", f"Timeout after {timeout}s"

