import asyncio
from .base import ToolError
from google import genai
from google.genai import types
import os
from pathlib import Path


class MultimediaReaderTool():
    def __init__(self, workspace_directory: str, gemini_client: genai.Client):
        self.workspace_directory = workspace_directory
        self.gemini_client = gemini_client
        self.definitions = [{
            "name": "multimedia_reader_tool",
            "description": "Uploads and grants Gemini access to multimedia files (such as .pdf, .jpg, .png, .mp4, etc.) for content analysis. Accepts a list of file paths relative to the workspace directory and uploads them to the Gemini Files API so that Gemini can read and process the contents of each file.",
            "parameters": {
                "type": "object",
                "properties": {
                "files": {
                    "type": "array",
                    "description": f"A list of relative file paths (from {self.workspace_directory}) for the multimedia files to upload and analyze. Supported formats include PDF, images (JPG, PNG, etc.), videos (MP4, etc.), and other common file types.",
                    "items": { "type": "string" }
                }
                },
                "required": ["files"]
            }
        }]
    
    async def __call__(
        self, 
        *,
        files: list[str],
        **kwargs,
    ):
        result_str = ""
        uploaded_files = []
        for relative_path in files:
            absolute_file_path = Path(os.path.join(self.workspace_directory, relative_path))
            if not absolute_file_path.exists():
                result_str += f"Error while reading file {relative_path} : file doesn't exist.\n"
                continue
            if absolute_file_path.is_dir():
                result_str += f"Error while reading file {relative_path} : path is a directory and not a file.\n"
                continue
            print(f"Uploading file {relative_path} ", end="")
            uploaded_file = self.gemini_client.files.upload(file=str(absolute_file_path))
            while uploaded_file.state.name == "PROCESSING":
                print('.', end='', flush=True)
                await asyncio.sleep(0.2)
                uploaded_file = self.gemini_client.files.get(name = uploaded_file.name)

            if uploaded_file.state.name == "FAILED":
                result_str += f"Error while uploading file {relative_path} : file can't be uploaded to Gemini Files API.\n"
                print("Upload Failed")
                continue
            print("success")
            result_str += f"File {relative_path} successfully uploaded."
            uploaded_files.append(uploaded_file)
        return [{
            "type": "text",
            "text": result_str
        },{
            "type": "uploaded_files",
            "files": uploaded_files
        }]                
