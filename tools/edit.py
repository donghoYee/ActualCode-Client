import asyncio
from collections import defaultdict
import os
from typing import Any, Literal, get_args
from pathlib import Path
from .base import ToolError
from .run import run

SNIPPET_LINES: int = 4


class EditTool():
    def __init__(self, workspace_directory: str):
        self.workspace_directory = workspace_directory
        self._file_history = defaultdict(list)
        self.definitions = [{
            "name": "text_editor_tool",
            "description": "Allows viewing, editing, creating, and inserting text in files and directories within the workspace directory.",
            "parameters": {
                "type": "object",
                "properties": {
                "command": {
                    "type": "string",
                    "enum": ["view", "str_replace", "create", "insert"],
                    "description": "The command to execute. Supported commands: 'view' (view file or directory contents), 'str_replace' (replace a string in a file), 'create' (create a new file), 'insert' (insert text into a file)."
                },
                "path": {
                    "type": "string",
                    "description": f"The relative path (from {self.workspace_directory}) to the file or directory to operate on. All file and directory references must be relative to {self.workspace_directory}."
                },
                "view_range": {
                    "type": "array",
                    "items": { "type": "integer" },
                    "minItems": 2,
                    "maxItems": 2,
                    "description": "Optional. Used only for the 'view' command on files. Specifies the [start, end] line numbers (1-indexed). Use -1 for the end value to indicate reading until the end of the file."
                },
                "old_str": {
                    "type": "string",
                    "description": "Required for the 'str_replace' command. The exact string to be replaced in the file, including any whitespace or indentation."
                },
                "new_str": {
                    "type": "string",
                    "description": "For the 'str_replace' and 'insert' commands. The text to insert into the file or use as a replacement."
                },
                "file_text": {
                    "type": "string",
                    "description": "Required for the 'create' command. The complete content to write into the newly created file."
                },
                "insert_line": {
                    "type": "integer",
                    "description": "Required for the 'insert' command. The line number after which the new text will be inserted (0 means insert at the beginning of the file)."
                }
                },
                "required": ["command", "path"]
            }
        }]
        
    
    async def __call__(
        self, 
        *,
        command: Literal["view", "create", "str_replace", "insert",],
        path: str,
        file_text: str | None = None,
        view_range: list[int] | None = None,
        old_str: str | None = None,
        new_str: str | None = None,
        insert_line: int | None = None,
        **kwargs,
    ):
        absolute_path = Path(os.path.join(self.workspace_directory, path))
        relative_path = path
        self.validate_path(command, absolute_path, relative_path)
        if command == "view":
            return await self.view(absolute_path, relative_path, view_range)
        elif command == "create":
            if file_text is None:
                raise ToolError("Parameter `file_text` is required for command: create")
            self.write_file(absolute_path, relative_path, file_text)
            self._file_history[relative_path].append(file_text)
            return {
                "type": "text",
                "text": f"File created successfully at: {relative_path}"
            }
        elif command == "str_replace":
            if old_str is None:
                raise ToolError(
                    "Parameter `old_str` is required for command: str_replace"
                )
            return self.str_replace(absolute_path, relative_path, old_str, new_str)
        elif command == "insert":
            if insert_line is None:
                raise ToolError(
                    "Parameter `insert_line` is required for command: insert"
                )
            if new_str is None:
                raise ToolError("Parameter `new_str` is required for command: insert")
            return self.insert(absolute_path, relative_path, insert_line, new_str)
        
        raise ToolError(
            f'Unrecognized command {command}. The allowed commands for the text_editor_tool tool are: {", ".join(["view", "create", "str_replace", "insert",])}'
        )
        
    def validate_path(self, command: str, absolute_path: Path, relative_path: str):
        """
        Check that the path/command combination is valid.
        """        
        # Check if path exists
        if not absolute_path.exists() and command != "create":
            raise ToolError(
                f"The path {relative_path} does not exist. Please provide a valid path."
            )
        if absolute_path.exists() and command == "create":
            raise ToolError(
                f"File already exists at: {relative_path}. Cannot overwrite files using command `create`."
            )
        # Check if the path points to a directory
        if absolute_path.is_dir():
            if command != "view":
                raise ToolError(
                    f"The path {relative_path} is a directory and only the `view` command can be used on directories"
                )
                
    
    async def view(self, absolute_path: Path, relative_path: str, view_range: list[int] | None = None):
        if absolute_path.is_dir():
            if view_range:
                raise ToolError(
                    "The `view_range` parameter is not allowed when `path` points to a directory."
                )

            _, stdout, stderr = await run(
                rf"cd {self.workspace_directory} && find {relative_path} -maxdepth 2 -not -path '*/\.*'"
            )
            if stderr:
                raise ToolError(stderr)
            stdout = f"Here's the files and directories up to 2 levels deep in {relative_path}, excluding hidden items:\n{stdout}\n"
            
            return {
                "type": "text",
                "text": stdout
            }

        file_content = self.read_file(absolute_path, relative_path)
        init_line = 1
        if view_range:
            if len(view_range) != 2 or not all(isinstance(i, int) for i in view_range):
                raise ToolError(
                    "Invalid `view_range`. It should be a list of two integers."
                )
            file_lines = file_content.split("\n")
            n_lines_file = len(file_lines)
            init_line, final_line = view_range
            if init_line < 1 or init_line > n_lines_file:
                raise ToolError(
                    f"Invalid `view_range`: {view_range}. Its first element `{init_line}` should be within the range of lines of the file: {[1, n_lines_file]}"
                )
            if final_line > n_lines_file:
                raise ToolError(
                    f"Invalid `view_range`: {view_range}. Its second element `{final_line}` should be smaller than the number of lines in the file: `{n_lines_file}`"
                )
            if final_line != -1 and final_line < init_line:
                raise ToolError(
                    f"Invalid `view_range`: {view_range}. Its second element `{final_line}` should be larger or equal than its first `{init_line}`"
                )

            if final_line == -1:
                file_content = "\n".join(file_lines[init_line - 1 :])
            else:
                file_content = "\n".join(file_lines[init_line - 1 : final_line])

        return {
                "type": "text",
                "text": self._make_output(file_content, relative_path, init_line=init_line)
        }
    
        
    def read_file(self, absolute_path: Path, relative_path: str):
        """Read the content of a file from a given path; raise a ToolError if an error occurs."""
        try:
            return absolute_path.read_text()
        except Exception as e:
            raise ToolError(f"Ran into {e} while trying to read {relative_path}") from None
        
    def write_file(self, absolute_path: Path, relative_path: str, file: str):
        """Write the content of a file to a given path; raise a ToolError if an error occurs."""
        try:
            absolute_path.write_text(file)
        except Exception as e:
            raise ToolError(f"Ran into {e} while trying to write to {relative_path}") from None
        
        
    def str_replace(self, absolute_path: Path, relative_path: str, old_str: str, new_str: str | None):
        """Implement the str_replace command, which replaces old_str with new_str in the file content"""
        # Read the file content
        file_content = self.read_file(absolute_path, relative_path).expandtabs()
        old_str = old_str.expandtabs()
        new_str = new_str.expandtabs() if new_str is not None else ""

        # Check if old_str is unique in the file
        occurrences = file_content.count(old_str)
        if occurrences == 0:
            raise ToolError(
                f"No replacement was performed, old_str `{old_str}` did not appear verbatim in {relative_path}."
            )
        elif occurrences > 1:
            file_content_lines = file_content.split("\n")
            lines = [
                idx + 1
                for idx, line in enumerate(file_content_lines)
                if old_str in line
            ]
            raise ToolError(
                f"No replacement was performed. Multiple occurrences of old_str `{old_str}` in lines {lines}. Please ensure it is unique"
            )

        # Replace old_str with new_str
        new_file_content = file_content.replace(old_str, new_str)

        # Write the new content to the file
        self.write_file(absolute_path, relative_path, new_file_content)

        # Save the content to history
        self._file_history[relative_path].append(file_content)

        # Create a snippet of the edited section
        replacement_line = file_content.split(old_str)[0].count("\n")
        start_line = max(0, replacement_line - SNIPPET_LINES)
        end_line = replacement_line + SNIPPET_LINES + new_str.count("\n")
        snippet = "\n".join(new_file_content.split("\n")[start_line : end_line + 1])

        # Prepare the success message
        success_msg = f"The file {relative_path} has been edited. "
        success_msg += self._make_output(
            snippet, f"a snippet of {relative_path}", start_line + 1
        )
        success_msg += "Review the changes and make sure they are as expected. Edit the file again if necessary."

        return {
            "type": "text",
            "text": success_msg
        }
    
    def insert(self, absolute_path: Path, relative_path: str, insert_line: int, new_str: str):
        """Implement the insert command, which inserts new_str at the specified line in the file content."""
        file_text = self.read_file(absolute_path, relative_path).expandtabs()
        new_str = new_str.expandtabs()
        file_text_lines = file_text.split("\n")
        n_lines_file = len(file_text_lines)

        if insert_line < 0 or insert_line > n_lines_file:
            raise ToolError(
                f"Invalid `insert_line` parameter: {insert_line}. It should be within the range of lines of the file: {[0, n_lines_file]}"
            )

        new_str_lines = new_str.split("\n")
        new_file_text_lines = (
            file_text_lines[:insert_line]
            + new_str_lines
            + file_text_lines[insert_line:]
        )
        snippet_lines = (
            file_text_lines[max(0, insert_line - SNIPPET_LINES) : insert_line]
            + new_str_lines
            + file_text_lines[insert_line : insert_line + SNIPPET_LINES]
        )

        new_file_text = "\n".join(new_file_text_lines)
        snippet = "\n".join(snippet_lines)

        self.write_file(absolute_path, relative_path, new_file_text)
        self._file_history[relative_path].append(file_text)

        success_msg = f"The file {relative_path} has been edited. "
        success_msg += self._make_output(
            snippet,
            "a snippet of the edited file",
            max(1, insert_line - SNIPPET_LINES + 1),
        )
        success_msg += "Review the changes and make sure they are as expected (correct indentation, no duplicate lines, etc). Edit the file again if necessary."
        return {
            "type": "text",
            "text": success_msg
        }
        
        
    def _make_output(
        self,
        file_content: str,
        file_descriptor: str,
        init_line: int = 1,
        expand_tabs: bool = True,
    ):
        """Generate output for the CLI based on the content of a file."""
        if expand_tabs:
            file_content = file_content.expandtabs()
        file_content = "\n".join(
            [
                f"{i + init_line:6}\t{line}"
                for i, line in enumerate(file_content.split("\n"))
            ]
        )
        return (
            f"Here's the result of running `cat -n` on {file_descriptor}:\n"
            + file_content
            + "\n"
        )