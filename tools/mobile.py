import aiohttp
import asyncio
import time
import os



class MobileTool:
    def __init__(self):
        self.definitions = [{
            "name": "request_photo_tool",
            "description": "Request the user to take a picture of something using their phone. Will receive the picture taken as output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "instruction": {
                        "type": "string",
                        "description": "Instruction for the user explaining what and how to take the photo. It should sound like a real human with a kind tone."
                    }
                },
            "required": ["instruction",]
            }
        }, {
            "name": "request_video_tool", 
            "description": "Request the user to take a video of something using their phone. Will receive the video taken as output.",
            "parameters": {
            "type": "object",
                "properties": {
                    "instruction": {
                        "type": "string",
                        "description": "Instruction for the user explaining what and how to take the video. It should sound like a real human with a kind tone."
                    },
                    "fps": {
                        "type": "integer",
                        "description": "Frame-rate used to analyze the video. Can be of range 1~10. Use higher fps when you want to analyze fast movements. Defaults to 1."
                    }
                },
            "required": ["instruction"]
            }
        }]
        self.send_notification_url = 'https://api.actualcode.org/send_notification'
        self.fetch_status_url = 'https://api.actualcode.org/fetch_notification_status'
        self.actualcode_api_key = os.environ["ACTUALCODE_API_KEY"]


    async def make_request(self, session: aiohttp.ClientSession, url: str, data: dict) -> dict:
        async with session.post(url, data=data) as response:
            return await response.json()


    async def request_photo_tool(self, instruction: str, timeout=60*10) -> list:
        notification_data = {
            "notification_type": "image",
            "instruction": instruction,
            "actualcode_api_token": self.actualcode_api_key,
        }
        async with aiohttp.ClientSession() as session:
            notification_response = await self.make_request(session, self.send_notification_url, notification_data)
            notification_id = notification_response["notification_id"]

            startTime = time.time()
            print(f"Waiting for photo", end="")
            while time.time() - startTime < timeout:
                status_request_data = {
                    "notification_id": notification_id,
                }
                status_response = await self.make_request(session, self.fetch_status_url, status_request_data)
                notification_status = status_response["notification_status"]
                if notification_status == "waiting":
                    await asyncio.sleep(1)
                    print(".", end="", flush=True)
                    continue
                elif notification_status == "done":
                    file_url = status_response["data"]["file_url"]
                    print("Photo taken!")
                    return {
                        "type": "image",
                        "file_url": file_url
                    }
                else:
                    return {
                        "type": "text",
                        "text": f"Error in request_photo_tool. Status: {notification_status}"
                    }
            return {
                "type": "text",
                "text": f"Error in request_photo_tool. Reason: timed out while waiting for photo"
            }

    async def request_video_tool(self, instruction: str, fps=1, timeout=60*10) -> list:
        notification_data = {
            "notification_type": "video",
            "instruction": instruction,
            "actualcode_api_token": self.actualcode_api_key,
        }
        async with aiohttp.ClientSession() as session:
            notification_response = await self.make_request(session, self.send_notification_url, notification_data)
            notification_id = notification_response["notification_id"]

            startTime = time.time()
            print("Waiting for video", end="")
            while time.time() - startTime < timeout:
                status_request_data = {
                    "notification_id": notification_id,
                }
                status_response = await self.make_request(session, self.fetch_status_url, status_request_data)
                notification_status = status_response["notification_status"]
                if notification_status == "waiting":
                    await asyncio.sleep(1)
                    print(".", end="", flush=True)
                    continue
                elif notification_status == "done":
                    file_url = status_response["data"]["file_url"]
                    print("Video taken!")
                    return {
                        "type": "video",
                        "file_url": file_url,
                        "fps": fps
                    }
                else:
                    return {
                        "type": "text",
                        "text": f"Error in request_video_tool. Status: {notification_status}"
                    }
            return {
                "type": "text",
                "text": f"Error in request_video_tool. Reason: timed out while waiting for video"
            }

if __name__ == "__main__":
    mobileTool = MobileTool()
    result = asyncio.run(mobileTool.request_video_tool("What is that?"))
    print(result)




    

    