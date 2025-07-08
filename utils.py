import pickle
import os
import time
import logging
import aiohttp
import aiofiles
import asyncio
from urllib.parse import urlparse
from tools.run import run
import platform, socket, re, uuid, json, psutil


def load_messages(file_path: str) -> list:
    startTime = time.time()
    if not os.path.exists(file_path): return []
    with open(file_path, "rb") as f:
        messages = pickle.load(f)
        logging.warning(f"loading messages took {time.time() - startTime}")
        return messages


def save_messages(file_path: str, messages: list) -> None:
    startTime = time.time()
    with open(file_path, "wb") as f:
        pickle.dump(messages, f)
        logging.warning(f"saving messages to disk took {time.time() - startTime}")
        return 
    
    
import os
import aiohttp
import aiofiles
import asyncio
from urllib.parse import urlparse

async def download_file(session, url, folder):
    try:
        # Get filename from URL
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)
        if not filename:
            filename = "downloaded_file"
        dest_path = os.path.join(folder, filename)

        async with session.get(url) as response:
            response.raise_for_status()
            async with aiofiles.open(dest_path, mode='wb') as f:
                async for chunk in response.content.iter_chunked(1024):
                    await f.write(chunk)
        logging.warning(f"Downloaded {url} → {dest_path}")
        return dest_path
    except Exception as e:
        logging.warning(f"Failed to download {url}: {e}")
        return None

async def download_files(urls, folder):
    os.makedirs(folder, exist_ok=True)
    async with aiohttp.ClientSession() as session:
        tasks = [download_file(session, url, folder) for url in urls]
        return await asyncio.gather(*tasks)



async def workspace_files(workspace_directory: str):
    _, stdout, stderr = await run(
        rf"cd {workspace_directory} && find ./ -maxdepth 2 -not -path '*/\.*'"
    )
    outputStr = f"Here's the files and directories up to 2 levels deep in workspace directory({workspace_directory}), excluding hidden items:\n{stdout}\n"
    return outputStr




def getSystemInfo():
    try:
        info={}
        info['platform']=platform.system()
        info['platform-release']=platform.release()
        info['platform-version']=platform.version()
        info['architecture']=platform.machine()
        info['hostname']=socket.gethostname()
        info['ip-address']=socket.gethostbyname(socket.gethostname())
        info['mac-address']=':'.join(re.findall('..', '%012x' % uuid.getnode()))
        info['processor']=platform.processor()
        info['ram']=str(round(psutil.virtual_memory().total / (1024.0 **3)))+" GB"
        return info
    except Exception as e:
        logging.exception(e)
        

if __name__ == "__main__":
    print(getSystemInfo())