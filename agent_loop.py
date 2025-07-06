from google import genai
from google.genai import types
import utils
from tools import mobile
import prompt
import logging
from google.genai import types
import requests

MAX_ITER = 50


async def run_agent(user_prompt: str, messages: list, messages_file_path: str) -> list: 
    client = genai.Client()
    mobileTool = mobile.MobileTool()
    function_declarations = mobileTool.definitions
    tools = types.Tool(function_declarations=function_declarations)
    config = types.GenerateContentConfig(tools=[tools], 
                                         system_instruction=prompt.SYSTEM_PROMPT,
                                         automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    chat = client.chats.create(model="gemini-2.5-flash", config=config, history=messages)
    parts =[types.Part(text=user_prompt)]
    response = chat.send_message(parts)
    print(response.text)

    messages = chat.get_history()
    utils.save_messages(messages_file_path, messages)
    
    iter = 0
    while iter < MAX_ITER:
        iter += 1
        logging.info(f"In Agent Loop iter: {iter}")
        function_call_datas = response.function_calls
        if not function_call_datas: break
        parts = []
        for function_call_data in function_call_datas:
            function_args = function_call_data.args
            function_name = function_call_data.name
            if function_name == "request_photo_tool":
                request_photo_tool_result = await mobileTool.request_photo_tool(function_args["instruction"], 60*10)
                if request_photo_tool_result["type"] == "text":
                    parts.append(types.Part.from_function_response(
                        name=function_name,
                        response={"result": request_photo_tool_result["text"]},
                    ))
                elif request_photo_tool_result["type"] == "image":
                    parts.append(types.Part.from_function_response(
                        name=function_name,
                        response={"result": "done"},
                    ))
                    image_bytes = requests.get(request_photo_tool_result["file_url"]).content
                    image = types.Part.from_bytes(
                        data=image_bytes, mime_type="image/jpeg"
                    )
                    parts.append(image)
        response = chat.send_message(parts)
        print(response.text)
        messages = chat.get_history()
        utils.save_messages(messages_file_path, messages)


    
    return messages