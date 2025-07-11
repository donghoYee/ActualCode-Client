from google import genai
from google.genai import types
import utils
from tools import mobile, edit, bash, search, web_fetch, multimedia_reader
from tools.base import ToolError
import prompt
import logging
from google.genai import types
import requests
import os
import asyncio
import time

MAX_ITER = 50


async def run_agent(user_prompt: str, messages: list, workspace_directory: str) -> list: 
    messages_file_path = os.path.join(workspace_directory, ".actualCodeMessagesData")
    client = genai.Client()
    mobileTool = mobile.MobileTool()
    editTool = edit.EditTool(workspace_directory)
    bashTool = bash.BashTool(workspace_directory)
    searchTool = search.SearchTool(workspace_directory, client)
    webFetchTool = web_fetch.WebFetchTool(workspace_directory, client)
    multimediaReaderTool = multimedia_reader.MultimediaReaderTool(workspace_directory, client)
    
    function_declarations = mobileTool.definitions + editTool.definitions + bashTool.definitions + searchTool.definitions + webFetchTool.definitions + multimediaReaderTool.definitions
    tools = types.Tool(function_declarations=function_declarations)
    config = types.GenerateContentConfig(tools=[tools, ], 
                                         system_instruction=prompt.SYSTEM_PROMPT, 
                                         temperature=0.0,
                                         #media_resolution="MEDIA_RESOLUTION_HIGH", # this doesn't work?                                 
    )
    
    workspace_files = await utils.workspace_files(workspace_directory)
    messages.append(types.Content(role="user", parts=[types.Part(text=workspace_files), types.Part(text=user_prompt)]))
    logging.warning("Calling Gemini")
    startTime = time.time()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=messages,
        config=config,
    )
    logging.warning(f"Gemini request completed in {time.time() - startTime} ")
    response_parts = response.candidates[0].content.parts
    if response_parts is None:
        logging.warning("Respond Parts is None...?")
        return messages
    messages.append(types.Content(role="model", parts = response_parts))
    utils.save_messages(messages_file_path, messages)
    print(response.text)
    
    iter = 0
    while iter < MAX_ITER:
        iter += 1
        logging.info(f"In Agent Loop iter: {iter}")
        function_call_datas = [response_part.function_call for response_part in response_parts if response_part.function_call is not None]
        if len(function_call_datas) == 0: break # No function called. Job done
        parts = []
        uploaded_files = []
        tasks = []
        
        for function_call_data in function_call_datas:
            function_args = function_call_data.args
            function_name = function_call_data.name
            if function_name == "request_photo_tool":
                tasks.append(handle_request_photo_tool(client, mobileTool, function_name, function_args, workspace_directory))
            elif function_name == "request_video_tool":
                tasks.append(handle_request_video_tool(client, mobileTool, function_name, function_args, workspace_directory))
            elif function_name == "text_editor_tool":
                tasks.append(handle_text_editor_tool(client, editTool, function_name, function_args, workspace_directory))
            elif function_name == "bash_tool":
                tasks.append(handle_bash_tool(client, bashTool, function_name, function_args, workspace_directory))
            elif function_name == "search_tool":
                tasks.append(handle_search_tool(client, searchTool, function_name, function_args, workspace_directory))
            elif function_name == "web_fetch_tool":
                tasks.append(handle_web_fetch_tool(client, webFetchTool, function_name, function_args, workspace_directory))
            elif function_name == "multimedia_reader_tool":
                tasks.append(handle_multimedia_reader_tool(client, multimediaReaderTool, function_name, function_args, workspace_directory))
            else:
                raise ValueError(f"Function {function_name} not found!") 
               
        results = await asyncio.gather(*tasks)
        for new_parts, new_uploaded_files in results:
            parts += new_parts
            uploaded_files += new_uploaded_files
            
        workspace_files = await utils.workspace_files(workspace_directory)
        messages.append(types.Content(role="user", parts=[types.Part(text=workspace_files)] + parts))
        messages += uploaded_files # Take care of uploaded files
        startTime = time.time()
        logging.warning("Calling Gemini")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=messages,
            config=config,
        )
        logging.warning(f"Gemini request completed in {time.time() - startTime} ")
        response_parts = response.candidates[0].content.parts
        if response_parts is None:
            logging.warning("Respond Parts is None...?")
            return messages
        messages.append(types.Content(role="model", parts = response_parts))
        utils.save_messages(messages_file_path, messages)
        print(response.text)


    
    return messages



async def handle_request_photo_tool(client: genai.Client, mobileTool: mobile.MobileTool, function_name: str,function_args: dict, workspace_directory: str):
    logging.warning(f"Function {function_name} called. Args: {function_args}")
    parts = []
    request_photo_tool_result = await mobileTool.request_photo_tool(function_args["instruction"], 60*10)
    uploaded_file = None
    if request_photo_tool_result["type"] == "text":
        parts.append(types.Part.from_function_response(
            name=function_name,
            response={"result": request_photo_tool_result["text"]},
        ))
    elif request_photo_tool_result["type"] == "image":
        parts.append(types.Part.from_function_response(
            name=function_name,
            response={"result": "Photo Uploaded"},
        ))
        file_url = request_photo_tool_result["file_url"]
        download_directory = os.path.join(workspace_directory, ".actualCodeDownloads")
        image_file_path = (await utils.download_files([file_url], download_directory))[0]
        uploaded_file = client.files.upload(file=image_file_path)
        while uploaded_file.state.name == "PROCESSING":
            print('.', end='', flush=True)
            await asyncio.sleep(0.2)
            uploaded_file = client.files.get(name = uploaded_file.name)
        print()

        if uploaded_file.state.name == "FAILED":
            raise ValueError(uploaded_file.state.name)
        
    return parts, [uploaded_file,]


async def handle_request_video_tool(client: genai.Client, mobileTool: mobile.MobileTool, function_name: str,function_args: dict, workspace_directory: str):
    logging.warning(f"Function {function_name} called. Args: {function_args}")
    parts = []
    request_video_tool_result = await mobileTool.request_video_tool(function_args["instruction"], function_args.get("fps", 1), 60*10)
    uploaded_file = None
    if request_video_tool_result["type"] == "text":
        parts.append(types.Part.from_function_response(
            name=function_name,
            response={"result": request_video_tool_result["text"]},
        ))
    elif request_video_tool_result["type"] == "video":
        parts.append(types.Part.from_function_response(
            name=function_name,
            response={"result": "Video Uploaded"},
        ))
        file_url = request_video_tool_result["file_url"]
        download_directory = os.path.join(workspace_directory, ".actualCodeDownloads")
        video_file_path = (await utils.download_files([file_url], download_directory))[0]
        uploaded_file = client.files.upload(file=video_file_path)
        while uploaded_file.state.name == "PROCESSING":
            print('.', end='', flush=True)
            await asyncio.sleep(0.2)
            uploaded_file = client.files.get(name = uploaded_file.name)
        print()

        if uploaded_file.state.name == "FAILED":
            raise ValueError(uploaded_file.state.name)
        print(f"FPS: {function_args.get('fps', 1)}")
        
    return parts, [uploaded_file, ]


async def handle_text_editor_tool(client: genai.Client, editTool: edit.EditTool, function_name: str, function_args: dict, workspace_directory: str):
    logging.warning(f"""Function {function_name} called. Command: {function_args["command"]}, Path: {function_args["path"]}""")
    parts = []
    try:
        result = await editTool(**function_args)
    except ToolError as e:
        parts.append(types.Part.from_function_response(
            name=function_name,
            response={"error": e.message},
        ))
        return parts, []
    parts.append(types.Part.from_function_response(
            name=function_name,
            response={"result": result["text"]},
    ))
    return parts, []


async def handle_bash_tool(client: genai.Client, bashTool: bash.BashTool, function_name: str, function_args: dict, workspace_directory: str):
    logging.warning(f"Function {function_name} called. Args: {function_args}")
    parts = []
    try:
        result = await bashTool(**function_args)
    except ToolError as e:
        parts.append(types.Part.from_function_response(
            name=function_name,
            response={"error": e.message},
        ))
        return parts, []
    parts.append(types.Part.from_function_response(
            name=function_name,
            response={"result": result["text"]},
    ))
    print(f"Bash {result['text']}")
    return parts, []


async def handle_search_tool(client: genai.Client, searchTool: search.SearchTool, function_name: str, function_args: dict, workspace_directory: str):
    logging.warning(f"Function {function_name} called. Args: {function_args}")
    parts = []
    try:
        result = await searchTool(**function_args)
    except ToolError as e:
        parts.append(types.Part.from_function_response(
            name=function_name,
            response={"error": e.message},
        ))
        return parts, []
    parts.append(types.Part.from_function_response(
            name=function_name,
            response={"result": result["text"]},
    ))
    logging.warning(f"Search complete.")
    print(result["text"])
    return parts, []


async def handle_web_fetch_tool(client: genai.Client, webFetchTool: web_fetch.WebFetchTool, function_name: str, function_args: dict, workspace_directory: str):
    logging.warning(f"Function {function_name} called. Args: {function_args}")
    parts = []
    try:
        result = await webFetchTool(**function_args)
    except ToolError as e:
        parts.append(types.Part.from_function_response(
            name=function_name,
            response={"error": e.message},
        ))
        return parts, []
    parts.append(types.Part.from_function_response(
            name=function_name,
            response={"result": result["text"]},
    ))
    logging.warning(f"Web fetch complete.")
    print(result["text"])
    return parts, []


async def handle_multimedia_reader_tool(client: genai.Client, multimediaReaderTool: multimedia_reader.MultimediaReaderTool, function_name: str, function_args: dict, workspace_directory: str):
    logging.warning(f"Function {function_name} called. Args: {function_args}")
    parts = []
    try:
        result = await multimediaReaderTool(**function_args)
    except ToolError as e:
        parts.append(types.Part.from_function_response(
            name=function_name,
            response={"error": e.message},
        ))
        return parts, []
    parts.append(types.Part.from_function_response(
            name=function_name,
            response={"result": result[0]["text"]},
    ))
    logging.warning(f"Web fetch complete.")
    print(result[0]["text"])
    return parts, result[1]["files"]


