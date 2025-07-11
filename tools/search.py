import asyncio
import os
from typing import Any, Literal
from google import genai
from google.genai import types

from .base import ToolError


class SearchTool():
    def __init__(self, workspace_directory: str, gemini_client: genai.Client):
        self.workspace_directory = workspace_directory
        self.gemini_client = gemini_client
        self.definitions = [{
            "name": "search_tool",
            "description": 'Performs a web search using Google Search (via the Gemini API) and returns the results. This tool is useful for finding information on the internet based on a query.',
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": 'string',
                        "description": 'The search query to find information on the web.',
                    },
                },
                "required": ["query"]
            }
        }]
        
    async def __call__(self, query: str, **kwargs):
        # Define the grounding tool
        grounding_tool = types.Tool(
            google_search=types.GoogleSearch()
        )
        tool_config = types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode="ANY", 
            )
        )
        # Configure generation settings
        config = types.GenerateContentConfig(
            tools=[grounding_tool],
            tool_config=tool_config,
        )
        
        # Make the request
        response = self.gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=query,
            config=config,
        )
        response_text = response.text
        response_dict = response.to_json_dict()
        grounding_metadata = response_dict.get("candidates", [{}])[0].get("grounding_metadata", {})
        sources = grounding_metadata.get("grounding_chunks")
        grounding_supports = grounding_metadata.get("grounding_supports")
        rendered_content = (
            grounding_metadata.get("search_entry_point", {}).get("rendered_content")
        )

        if not response_text or not response_text.strip():
            return {
                "type": "text",
                "text": f'No search results or information found for query: "{query}"',
            }

        modified_response_text = response_text
        source_list_formatted = []

        # Format sources as [N] Title (URI)
        if sources and len(sources) > 0:
            for idx, source in enumerate(sources):
                title = source.get("web", {}).get("title", "Untitled")
                uri = source.get("web", {}).get("uri", "No URI")
                source_list_formatted.append(f"[{idx + 1}] {title} ({uri})")

            # Add inline citations
            if grounding_supports and len(grounding_supports) > 0:
                insertions = []
                for support in grounding_supports:
                    segment = support.get("segment")
                    chunk_indices = support.get("grounding_chunk_indices")
                    if segment and chunk_indices:
                        citation_marker = "".join(
                            [f"[{chunk_index + 1}]" for chunk_index in chunk_indices]
                        )
                        insertions.append(
                            {"index": segment["end_index"], "marker": citation_marker}
                        )

                # Sort by index descending so insertions don't shift text
                insertions.sort(key=lambda x: -x["index"])
                response_chars = list(modified_response_text)
                for insertion in insertions:
                    response_chars.insert(insertion["index"], insertion["marker"])
                modified_response_text = "".join(response_chars)

        # Prepare Sources section with rendered content
        sources_section = ""
        if source_list_formatted:
            sources_section += "\n\nSources:\n" + "\n".join(source_list_formatted)
            
        ## It seems we don't need that
        # if rendered_content:
        #     sources_section += "\n\nSearch Widget Preview:\n" + rendered_content

        modified_response_text += sources_section

        return {
            "type": "text",
            "text": f'Web search results for "{query}":\n\n{modified_response_text}',
        }
    
    


     