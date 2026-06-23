# agent/slack_reader.py
from slack_sdk import WebClient


def read_channel_history(token, channel, limit=200):
    client = WebClient(token=token)
    history = client.conversations_history(channel=channel, limit=limit)
    messages = history.get("messages", [])
    user_map = {}
    for u in client.users_list().get("members", []):
        user_map[u["id"]] = u.get("profile", {}).get("display_name") or u.get("name") or u["id"]
    return messages, user_map
