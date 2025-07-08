import asyncio
import re
import aiohttp
from google import genai
from google.genai import types

from .base import ToolError

def extract_urls(text):
    url_regex = r'(https?://[^\s]+)'
    return re.findall(url_regex, text or '')

def extract_url_metadata(url_context_metadata):
    """
    Extracts and formats retrieved URLs and their status for reporting.
    """
    url_metadata = url_context_metadata.get("url_metadata", [])
    if not url_metadata:
        return ""
    url_lines = []
    for idx, meta in enumerate(url_metadata):
        url = meta.get("retrieved_url", "Unknown URL")
        status = str(meta.get("url_retrieval_status", "Unknown Status"))
        url_lines.append(f"[{idx+1}] {url} ({status})")
    return "\n".join(url_lines)

class WebFetchTool():
    def __init__(self, workspace_directory: str, gemini_client: genai.Client):
        self.workspace_directory = workspace_directory
        self.gemini_client = gemini_client
        self.definitions = [{
            "name": "web_fetch_tool",
            "description": (
                "Fetches and processes content from up to 20 URLs (including localhost and private addresses) provided in the prompt, using the Gemini API. "
                "Include instructions in the prompt for how the content should be processed (e.g., 'summarize', 'extract key points'). "
                "If Gemini cannot retrieve the content, falls back to direct HTTP fetch and asks Gemini to process the raw text content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": (
                            "A prompt containing up to 20 URLs (http(s)://) and instructions for what to do with their content. "
                            "For example: 'Summarize https://example.com and extract data from https://another.com/data'."
                        ),
                    },
                },
                "required": ["prompt"]
            }
        }]

    async def __call__(self, prompt: str, **kwargs):
        # Tool call: tries Gemini API with urlContext first
        grounding_tool = types.Tool(url_context=types.UrlContext())
        tool_config = types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode="ANY")
        )
        config = types.GenerateContentConfig(
            tools=[grounding_tool],
            tool_config=tool_config,
        )

        # Make Gemini request
        try:
            response = self.gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=config,
            )
        except Exception as ex:
            return await self._fallback_fetch(prompt, f"Gemini error: {ex}")

        response_text = response.text
        response_dict = response.to_json_dict()
        candidate = response_dict.get("candidates", [{}])[0]
        grounding_metadata = candidate.get("grounding_metadata", {})
        url_context_meta = candidate.get("url_context_metadata", {})
        sources = grounding_metadata.get("grounding_chunks")
        grounding_supports = grounding_metadata.get("grounding_supports")
        
        # Error Handling
        processing_error = False
        url_meta = url_context_meta.get("url_metadata")
        if url_meta and len(url_meta) > 0:
            all_statuses = [m.get("url_retrieval_status") for m in url_meta]
            if all(s != "URL_RETRIEVAL_STATUS_SUCCESS" for s in all_statuses):
                processing_error = True
        elif (not response_text.strip()) and (not sources or len(sources) == 0):
            processing_error = True

        if (
            not processing_error
            and not response_text.strip()
            and (not sources or len(sources) == 0)
        ):
            processing_error = True

        if processing_error:
            return await self._fallback_fetch(prompt, "Gemini was unable to retrieve content for the given URLs.")

        # Build sources and citations
        modified_response_text = response_text
        source_list_formatted = []
        if sources and len(sources) > 0:
            for idx, source in enumerate(sources):
                title = source.get("web", {}).get("title", "Untitled")
                uri = source.get("web", {}).get("uri", "Unknown URI")
                source_list_formatted.append(f"[{idx + 1}] {title} ({uri})")

            # Inline citations
            if grounding_supports and len(grounding_supports) > 0:
                insertions = []
                for support in grounding_supports:
                    segment = support.get("segment")
                    chunk_indices = support.get("grounding_chunk_indices")
                    if segment and chunk_indices:
                        citation_marker = "".join([f"[{chunk_index + 1}]" for chunk_index in chunk_indices])
                        insertions.append({
                            "index": segment["end_index"],
                            "marker": citation_marker,
                        })
                insertions.sort(key=lambda x: -x["index"])
                response_chars = list(modified_response_text)
                for insertion in insertions:
                    response_chars.insert(insertion["index"], insertion["marker"])
                modified_response_text = "".join(response_chars)

        # Prepare sources and fetched URLs section
        sources_section = ""
        if source_list_formatted:
            sources_section += "\n\nSources:\n" + "\n".join(source_list_formatted)

        fetched_urls_section = ""
        if url_context_meta:
            fetched_urls = extract_url_metadata(url_context_meta)
            if fetched_urls:
                fetched_urls_section += "\n\nFetched URLs:\n" + fetched_urls

        modified_response_text += sources_section + fetched_urls_section

        return {
            "type": "text",
            "text": f'Web fetch results for prompt:\n\n{modified_response_text}',
        }

    async def _fallback_fetch(self, prompt, error_message):
        urls = extract_urls(prompt)
        if not urls:
            return {
                "type": "text",
                "text": "Error: No URL found in the prompt.",
            }
        url = urls[0]
        # GitHub blob->raw conversion
        if "github.com" in url and "/blob/" in url:
            url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status != 200:
                        raise Exception(f"Fetch failed: HTTP {resp.status}")
                    html = await resp.text()
                    # Strip tags: very basic, not full-featured
                    text = re.sub(r'<[^>]+>', '', html)[:100000]
        except Exception as ex:
            return {
                "type": "text",
                "text": f"Error during fallback fetch for {url}: {ex}",
            }
        # Ask Gemini to process raw content
        fallback_prompt = f"""The user requested: "{prompt}"

I was unable to access the URL directly. Instead, I have fetched the raw content of the page. Please use the following content to answer the user's request. Do not attempt to access the URL again.

---
{text}
---
"""
        try:
            response = self.gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=fallback_prompt,
            )
            fallback_response_text = response.text or ''
        except Exception as ex:
            return {
                "type": "text",
                "text": f"Error: Could not process fallback content for {url}: {ex}",
            }
        return {
            "type": "text",
            "text": fallback_response_text or f"Fetched and processed content for {url}."
        }

