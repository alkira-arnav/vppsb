import logging
import sys
import re
import os

from os.path import dirname, join
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from time import sleep

from yaml_utils import load_yaml

# Create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
logger.addHandler(handler)


def retry(tries=3, delay=1):
    """
    Decorator to retry a function with constant delay between attempts
    Runs the function `tries` times in the worst case
    """

    def decorator(fn):
        def wrapper_fn(*args, **kwargs):
            attempt = 0
            while attempt < tries:
                code, resp = fn(*args, **kwargs)
                if code:
                    return code, resp

                attempt += 1
                logger.error(f"Function {fn.__name__} failed. Attempt {attempt} out of {tries}")
                sleep(delay)
            return code, resp

        return wrapper_fn

    return decorator


class SlackUtils:
    def __init__(self):
        self.max_text_len = 4000
        self.block_max_header_len = 150
        self.block_max_text_len = 3000
        self.block_max_field_len = 2000

        self.__load_slack()

    def __load_slack(self, file_path=None):
        """
        Fetch token from file and create a slack client
        """

        token = os.environ.get("bot_token")
        if token is None:
            logger.error("Missing slack bot token in %s", file_path)
            sys.exit(1)

        self.slack_client = WebClient(token=token)
        logger.debug("Created slack web client")

    def construct_text_blocks(self, text):
        """
        Split text into chunks of size <= max_len and return a list of blocks
        """
        return [
            {"type": "section", "text": {"type": "mrkdwn", "text": chunk}}
            for chunk in [
                text[i : i + self.block_max_text_len]
                for i in range(0, len(text), self.block_max_text_len)
            ]
        ]

    def construct_field_blocks(self, dictionary):
        """
        Turn each entry in the dictionary into a string "*key:* val". If this
        string is longer than max_len truncate it. Return a list of field blocks
        that contain these strings
        """
        # Format and truncate the entries
        entries = [f"*{key}:* {val}" for key, val in dictionary.items()]
        entries = [
            text[: self.block_max_field_len - 3] + "..."
            if len(text) > self.block_max_field_len
            else text
            for text in entries
        ]

        # Construct blocks
        blocks = []
        section = {"type": "section", "fields": []}
        for text in entries:
            section["fields"].append({"type": "mrkdwn", "text": text})

            # Field blocks are limited to 10 text blocks
            if len(section["fields"]) == 10:
                blocks.append(section)
                section = {"type": "section", "fields": []}

        if section["fields"]:
            blocks.append(section)

        return blocks

    def create_slack_message(self, channel, text, blocks=None):
        """
        Post a message on the passed channel
        Text is a string
        Optional: Blocks is a list https://api.slack.com/block-kit
        """
        logger.debug("Creating slack message on channel %s", channel)

        if blocks is None and len(text) > self.max_text_len:
            return self.create_long_slack_message(channel, text)

        @retry()
        def post_message(channel, text, blocks):
            try:
                resp = self.slack_client.chat_postMessage(channel=channel, text=text, blocks=blocks)
                return True, resp

            except SlackApiError as error:
                logger.exception("Exception occurred when creating slack message")
                return False, error

        code, resp = post_message(channel, text, blocks)
        if not code:
            return code, resp

        return True, resp

    def create_long_slack_message(self, channel, text):
        """
        Long messages in Slack are split into multiple messages which can disrupt code block
        formatting. This function splits long pieces of text into chunks and preserves code block
        formatting across these chunks. A code block is marked by ```
        """
        # Identify (start, end) for each code block in text
        code_block_indices = []

        inside_block, start = False, -1
        for match in re.finditer("```", text):
            if not inside_block:
                start, inside_block = match.start(), True
            else:
                code_block_indices.append((start, match.end()))
                inside_block = False

        # Split text into chunks while preserving code blocks
        text_chunks = [""]
        text_index = 0

        for line in [line + "\n" for line in text.split("\n") if line]:

            # If less then max length, add to current chunk
            if len(text_chunks[-1]) + len(line) <= self.max_text_len:
                text_chunks[-1] += line

            # If inside code block, preserve formatting and add new chunk
            elif any(filter(lambda range: range[0] <= text_index <= range[1], code_block_indices)):
                text_chunks[-1] += "```"
                text_chunks.append("```" + line)

            # Add new chunk
            else:
                text_chunks.append(line)

            text_index += len(line)

        # Send messages
        success = True
        for chunk in text_chunks:
            code, resp = self.create_slack_message(channel, chunk)
            if not code:
                success = False

        return success, resp
