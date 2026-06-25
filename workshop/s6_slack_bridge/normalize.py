import datetime

# Argentina (UTC-3, sin DST) — para que "hoy/ayer" tenga sentido local
AR_TZ = datetime.timezone(datetime.timedelta(hours=-3))


def _fecha(ts):
    try:
        return datetime.datetime.fromtimestamp(float(ts), AR_TZ).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return "?"


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
            # la fecha va EN el texto → el modelo puede responder "ayer", "hoy", etc.
            "id": f"{channel}-{ts}",
            "text": f"[{_fecha(ts)}] {author}: {text}",
            "channel": channel,
            "ts": ts,
            "author": author,
        })
    return docs
