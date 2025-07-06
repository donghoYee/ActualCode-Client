import argparse
import os
from pathlib import Path
import asyncio
import utils
from dotenv import load_dotenv
from agent_loop import run_agent
load_dotenv()


async def main(workspace_directory: str):
    messages_file_path = os.path.join(workspace_directory, ".actualCodeMessagesData")
    messages = utils.load_messages(messages_file_path)

    while True:
        user_prompt = input("What do you want to build?: \n")
        messages = await run_agent(user_prompt, messages, messages_file_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--directory", dest="directory", action="store", required=True)      
    args = parser.parse_args()
    directory_absolute = os.path.abspath(args.directory)
    Path(directory_absolute).mkdir(parents=True, exist_ok=True)
    asyncio.run(main(directory_absolute))
