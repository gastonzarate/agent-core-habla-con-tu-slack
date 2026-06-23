def normalize_messages(messages, user_map, channel):
    docs = []
    for m in messages:
        if m.get("type") != "message":
            continue
        if m.get("subtype"):  # joins, edits, bot_message, etc. — no es contenido real
            continue
        if m.get("bot_id"):  # mensajes de bots (incl. las propias respuestas) — evita ruido/loop
            continue
        text = (m.get("text") or "").strip()
        if not text:
            continue
        uid = m.get("user", "")
        author = user_map.get(uid, uid)
        ts = m["ts"]
        docs.append({
            "id": f"{channel}-{ts}",
            "text": f"{author}: {text}",
            "channel": channel,
            "ts": ts,
            "author": author,
        })
    return docs
