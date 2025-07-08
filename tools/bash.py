import asyncio
import os
from typing import Any, Literal

from .base import ToolError

class BashTool():
    def __init__(self, workspace_directory: str):
        self.workspace_directory = workspace_directory
        self._session = None
        self.definitions = [{
            "name": "bash_tool",
            "description": f"Execute Bash shell commands within a persistent session. The Bash session maintains state, including environment variables and working directory, between commands. All commands execute with the working directory set to {self.workspace_directory}. Use the 'restart' parameter to reset the shell session.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": f"The Bash command to execute. The command will run in a persistent Bash shell with its working directory set to {self.workspace_directory}. This is required unless 'restart' is true."
                    },
                    "restart": {
                        "type": "boolean",
                        "description": f"Set to true to restart the Bash shell session. When restarting, do not provide a command. Restarting will clear all environment variables and reset the working directory to {self.workspace_directory}."
                    }
                    },
                "required": []
                }
            }]

        
    async def __call__(
        self, command: str | None = None, restart: bool = False, **kwargs
    ):
        if restart:
            if self._session:
                self._session.stop()
            self._session = _BashSession(self.workspace_directory)
            await self._session.start()

            return {
                "type": "text",
                "text": "tool has been restarted."
            }

        if self._session is None:
            self._session = _BashSession(self.workspace_directory)
            await self._session.start()

        if command is not None:
            return await self._session.run(command)

        raise ToolError("no command provided.")
        
    
    
    
    

class _BashSession:
    """A session of a bash shell."""

    _started: bool
    _process: asyncio.subprocess.Process

    command: str = "/bin/bash"
    _output_delay: float = 0.2  # seconds
    _timeout: float = 120.0  # seconds
    _sentinel: str = "<<exit>>"

    def __init__(self, workspace_diretory: str):
        self._started = False
        self._timed_out = False
        self.workspace_directory = workspace_diretory

    async def start(self):
        if self._started:
            return

        self._process = await asyncio.create_subprocess_shell(
            self.command,
            preexec_fn=os.setsid,
            shell=True,
            bufsize=0,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.workspace_directory,
        )

        self._started = True

    def stop(self):
        """Terminate the bash shell."""
        if not self._started:
            raise ToolError("Session has not started.")
        if self._process.returncode is not None:
            return
        self._process.terminate()

    async def run(self, command: str):
        """Execute a command in the bash shell."""
        if not self._started:
            raise ToolError("Session has not started.")
        if self._process.returncode is not None:
            return {
                "type": "text",
                "text": f"Error: tool must be restarted. Bash has exited with returncode {self._process.returncode}"
            }
            
        if self._timed_out:
            raise ToolError(
                f"timed out: bash has not returned in {self._timeout} seconds and must be restarted",
            )

        # we know these are not None because we created the process with PIPEs
        assert self._process.stdin
        assert self._process.stdout
        assert self._process.stderr

        # send command to the process
        self._process.stdin.write(
            command.encode() + f"; echo '{self._sentinel}'\n".encode()
        )
        await self._process.stdin.drain()

        # read output from the process, until the sentinel is found
        try:
            print("Bash command in progress...")
            async with asyncio.timeout(self._timeout):
                while True:
                    await asyncio.sleep(self._output_delay)
                    # if we read directly from stdout/stderr, it will wait forever for
                    # EOF. use the StreamReader buffer directly instead.
                    output = self._process.stdout._buffer.decode()  # pyright: ignore[reportAttributeAccessIssue]
                    print(output, end="")
                    if self._sentinel in output:
                        # strip the sentinel and break
                        output = output[: output.index(self._sentinel)]
                        break
            print("Done")
        except asyncio.TimeoutError:
            self._timed_out = True
            raise ToolError(
                f"timed out: bash has not returned in {self._timeout} seconds and must be restarted",
            ) from None

        if output.endswith("\n"):
            output = output[:-1]

        error = self._process.stderr._buffer.decode()  # pyright: ignore[reportAttributeAccessIssue]
        if error.endswith("\n"):
            error = error[:-1]

        # clear the buffers so that the next output can be read correctly
        self._process.stdout._buffer.clear()  # pyright: ignore[reportAttributeAccessIssue]
        self._process.stderr._buffer.clear()  # pyright: ignore[reportAttributeAccessIssue]

        if error:
            return {
                "type": "text",
                "text": f"Output: {output}, Error: {error}."
            }
        return {
                "type": "text",
                "text": f"Output: {output}"
        }

    
