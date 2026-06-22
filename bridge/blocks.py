def build_slack_response(answer, citations):
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": answer}}]
    if citations:
        refs = ", ".join(c["id"] for c in citations)
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"📎 Fuentes: {refs}"}],
        })
    return {"response_type": "in_channel", "blocks": blocks}
