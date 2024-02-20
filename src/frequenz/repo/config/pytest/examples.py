# License: MIT
# Copyright © 2023 Frequenz Energy-as-a-Service GmbH

"""Utility to enable linting of code examples in docstrings.

Code examples are often wrapped in triple backticks (````python`) within our docstrings.
This plugin extracts these code examples and validates them using pylint.

The main utility function is
[`get_sybil_arguments()`][frequenz.repo.config.pytest.examples.get_sybil_arguments],
which returns a dictionary that can be used to pass to the [`Sybil()`][sybil.Sybil]
constructor.

You still need to create a `conftest.py` file in the root of your project's sources,
typically `src/conftest.py`, with the following contents:

```python
from frequenz.repo.config.pytest import examples
from sybil import Sybil

pytest_collect_file = Sybil(**examples.get_sybil_arguments()).pytest()
```
"""

import ast
import os
import subprocess
import textwrap
from pathlib import Path
from typing import Any

from sybil import Example
from sybil.evaluators.python import pad
from sybil.parsers.myst import CodeBlockParser

_PYLINT_DISABLE_COMMENT = (
    "# pylint: {}=unused-import,wildcard-import,unused-wildcard-import"
)

_FORMAT_STRING = """
# Generated auto-imports for code example
{disable_pylint}
{imports}
{enable_pylint}

{code}"""


def get_sybil_arguments() -> dict[str, Any]:
    """Get the arguments to pass when instantiating the Sybil object to lint docs examples.

    Returns:
        The arguments to pass when instantiating the Sybil object.
    """
    return {
        "parsers": [_CustomPythonCodeBlockParser()],
        "patterns": ["*.py"],
        # This is a hack because Sybil seems to have issues with `__init__.py` files.
        # See https://github.com/frequenz-floss/frequenz-repo-config-python/issues/113
        # for details
        "excludes": ["__init__.py"],
    }


def _get_import_statements(code: str) -> list[str]:
    """Get all import statements from a given code string.

    Args:
        code: The code to extract import statements from.

    Returns:
        A list of import statements.
    """
    tree = ast.parse(code)
    import_statements: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_statement = ast.get_source_segment(code, node)
            assert import_statement is not None
            import_statements.append(import_statement)

    return import_statements


def _path_to_import_statement(path: Path) -> str:
    """Convert a path to a Python file to an import statement.

    Args:
        path: The path to convert.

    Returns:
        The import statement.

    Raises:
        ValueError: If the path does not point to a Python file.
    """
    # Make the path relative to the present working directory
    if path.is_absolute():
        path = path.relative_to(Path.cwd())

    # Check if the path is a Python file
    if path.suffix != ".py":
        raise ValueError("Path must point to a Python file (.py)")

    # Remove 'src' prefix if present
    parts = path.parts
    if parts[0] == "src":
        parts = parts[1:]

    # Remove the '.py' extension and join parts with '.'
    module_path = ".".join(parts)[:-3]

    # Create the import statement
    import_statement = f"from {module_path} import *"
    return import_statement


class _CustomPythonCodeBlockParser(CodeBlockParser):
    """Code block parser that validates extracted code examples using pylint.

    This parser is a modified version of the default Python code block parser
    from the Sybil library.
    It uses pylint to validate the extracted code examples.

    All code examples are preceded by the original file's import statements as
    well as an wildcard import of the file itself.
    This allows us to use the code examples as if they were part of the original
    file.

    Additionally, the code example is padded with empty lines to make sure the
    line numbers are correct.

    Pylint warnings which are unimportant for code examples are disabled.
    """

    def __init__(self) -> None:
        """Initialize the parser."""
        super().__init__("python")

    def evaluate(self, example: Example) -> None | str:
        """Validate the extracted code example using pylint.

        Args:
            example: The extracted code example.

        Returns:
            None if the code example is valid, otherwise the pylint output.
        """
        # Get the import statements for the original file
        import_header = _get_import_statements(example.document.text)
        # Add a wildcard import of the original file
        import_header.append(
            _path_to_import_statement(Path(os.path.relpath(example.path)))
        )
        imports_code = "\n".join(import_header)

        # Dedent the code example
        # There is also example.parsed that is already prepared, but it has
        # empty lines stripped and thus fucks up the line numbers.
        example_code = textwrap.dedent(
            example.document.text[example.start : example.end]
        )
        # Remove first line (the line with the triple backticks)
        example_code = example_code[example_code.find("\n") + 1 :]

        example_with_imports = _FORMAT_STRING.format(
            disable_pylint=_PYLINT_DISABLE_COMMENT.format("disable"),
            imports=imports_code,
            enable_pylint=_PYLINT_DISABLE_COMMENT.format("enable"),
            code=example_code,
        )

        # Make sure the line numbers are correct
        source = pad(
            example_with_imports,
            example.line - imports_code.count("\n") - _FORMAT_STRING.count("\n"),
        )

        # pylint disable parameters
        pylint_disable_params = [
            "missing-module-docstring",
            "missing-class-docstring",
            "missing-function-docstring",
            "reimported",
            "unused-variable",
            "no-name-in-module",
            "await-outside-async",
        ]

        response = _validate_with_pylint(source, example.path, pylint_disable_params)

        if len(response) > 0:
            return (
                f"Pylint validation failed for code example:\n"
                f"{example_with_imports}\nOutput: " + "\n".join(response)
            )

        return None


def _validate_with_pylint(
    code_example: str, path: str, disable_params: list[str]
) -> list[str]:
    """Validate a code example using pylint.

    Args:
        code_example: The code example to validate.
        path: The path to the original file.
        disable_params: The pylint disable parameters.

    Returns:
        A list of pylint messages.
    """
    try:
        pylint_command = [
            "pylint",
            "--disable",
            ",".join(disable_params),
            "--from-stdin",
            path,
        ]

        subprocess.run(
            pylint_command,
            input=code_example,
            text=True,
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as exception:
        output = exception.output
        assert isinstance(output, str)
        return output.splitlines()

    return []
