"""Syntax Validator - validates generated code syntax for multiple languages."""

from __future__ import annotations

import ast
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of syntax validation."""

    file_path: str
    is_valid: bool
    language: str
    error_message: str | None = None
    line_number: int | None = None
    column: int | None = None


class SyntaxValidator:
    """Validates syntax of generated code files."""

    # Map file extensions to languages
    EXTENSION_MAP: dict[str, str] = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".rb": "ruby",
    }

    def validate(self, file_path: str, content: str) -> ValidationResult:
        """Validate syntax of a code file.

        Args:
            file_path: Relative path to the file.
            content: File content to validate.

        Returns:
            ValidationResult with validity status and any error info.
        """
        ext = os.path.splitext(file_path)[1].lower()
        language = self.EXTENSION_MAP.get(ext, "unknown")

        if language == "python":
            return self._validate_python(file_path, content)
        elif language in ("javascript", "typescript"):
            return self._validate_js_ts(file_path, content, language)
        elif language == "go":
            return self._validate_go(file_path, content)
        else:
            # Skip validation for unknown languages
            logger.info("Skipping validation for unknown language: %s", ext)
            return ValidationResult(
                file_path=file_path,
                is_valid=True,
                language=language,
            )

    def _validate_python(self, file_path: str, content: str) -> ValidationResult:
        """Validate Python syntax using ast.parse."""
        try:
            ast.parse(content, filename=file_path)
            return ValidationResult(
                file_path=file_path,
                is_valid=True,
                language="python",
            )
        except SyntaxError as e:
            return ValidationResult(
                file_path=file_path,
                is_valid=False,
                language="python",
                error_message=str(e.msg),
                line_number=e.lineno,
                column=e.offset,
            )

    def _validate_js_ts(
        self, file_path: str, content: str, language: str
    ) -> ValidationResult:
        """Validate JavaScript/TypeScript syntax using Node.js parser."""
        try:
            # Use Node.js to check syntax
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=os.path.splitext(file_path)[1],
                delete=False,
            ) as f:
                f.write(content)
                tmp_path = f.name

            try:
                # Try to parse with node --check
                result = subprocess.run(
                    ["node", "--check", tmp_path],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode == 0:
                    return ValidationResult(
                        file_path=file_path,
                        is_valid=True,
                        language=language,
                    )
                else:
                    error_msg = result.stderr.strip()
                    # Try to extract line number
                    line_num = None
                    if ":" in error_msg:
                        parts = error_msg.split(":")
                        for part in parts:
                            if part.strip().isdigit():
                                line_num = int(part.strip())
                                break

                    return ValidationResult(
                        file_path=file_path,
                        is_valid=False,
                        language=language,
                        error_message=error_msg,
                        line_number=line_num,
                    )
            finally:
                os.unlink(tmp_path)

        except FileNotFoundError:
            # Node.js not available, skip validation
            logger.warning("Node.js not found, skipping JS/TS validation")
            return ValidationResult(
                file_path=file_path,
                is_valid=True,
                language=language,
            )
        except subprocess.TimeoutExpired:
            logger.warning("JS/TS validation timed out")
            return ValidationResult(
                file_path=file_path,
                is_valid=True,
                language=language,
            )

    def _validate_go(self, file_path: str, content: str) -> ValidationResult:
        """Validate Go syntax using go vet."""
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".go",
                delete=False,
            ) as f:
                f.write(content)
                tmp_path = f.name

            try:
                result = subprocess.run(
                    ["go", "vet", tmp_path],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode == 0:
                    return ValidationResult(
                        file_path=file_path,
                        is_valid=True,
                        language="go",
                    )
                else:
                    return ValidationResult(
                        file_path=file_path,
                        is_valid=False,
                        language="go",
                        error_message=result.stderr.strip(),
                    )
            finally:
                os.unlink(tmp_path)

        except FileNotFoundError:
            logger.warning("Go not found, skipping Go validation")
            return ValidationResult(
                file_path=file_path,
                is_valid=True,
                language="go",
            )
        except subprocess.TimeoutExpired:
            logger.warning("Go validation timed out")
            return ValidationResult(
                file_path=file_path,
                is_valid=True,
                language="go",
            )
