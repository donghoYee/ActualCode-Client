from google import genai
from google.genai import types
import utils
from tools import mobile
import prompt
import logging
from google.genai import types
import requests
import os
import asyncio

MAX_ITER = 50


async def run_agent(user_prompt: str, messages: list, workspace_directory: str) -> list: 
    messages_file_path = os.path.join(workspace_directory, ".actualCodeMessagesData")
    client = genai.Client()
    mobileTool = mobile.MobileTool()
    function_declarations = mobileTool.definitions
    tools = types.Tool(function_declarations=function_declarations)
    config = types.GenerateContentConfig(tools=[tools], 
                                         system_instruction=prompt.SYSTEM_PROMPT,                                    
    )
    messages.append(types.Content(role="user", parts=[types.Part(text=user_prompt)]))
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=messages,
        config=config,
    )
    response_parts = response.candidates[0].content.parts
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
        for function_call_data in function_call_datas:
            function_args = function_call_data.args
            function_name = function_call_data.name
            if function_name == "request_photo_tool":
                parts, uploaded_file = await handle_request_photo_tool(client, mobileTool, function_name, function_args, parts, workspace_directory)
                if uploaded_file is not None: uploaded_files.append(uploaded_file)
            elif function_name == "request_video_tool":
                parts, uploaded_file = await handle_request_video_tool(client, mobileTool, function_name, function_args, parts, workspace_directory)
                if uploaded_file is not None: uploaded_files.append(uploaded_file)
        messages.append(types.Content(role="user", parts=parts))
        messages += uploaded_files # Take care of uploaded files
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=messages,
            config=config,
        )
        response_parts = response.candidates[0].content.parts
        messages.append(types.Content(role="model", parts = response_parts))
        utils.save_messages(messages_file_path, messages)
        print(response.text)


    
    return messages



async def handle_request_photo_tool(client: genai.Client, mobileTool: mobile.MobileTool, function_name: str,function_args: dict, parts: list, workspace_directory: str):
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
        
    return parts, uploaded_file


async def handle_request_video_tool(client: genai.Client, mobileTool: mobile.MobileTool, function_name: str,function_args: dict, parts: list, workspace_directory: str):
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
        print(f"FPS: {function_args.get("fps", 1)}")
        
    return parts, uploaded_file