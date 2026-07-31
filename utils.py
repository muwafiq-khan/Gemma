import json
import re


def parse_json(text):
    if text is None:
        return None
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*\]", "]", text)
    for attempt in [json.loads, lambda t: json.JSONDecoder().raw_decode(t)[0]]:
        try:
            return attempt(text)
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    start = text.find("{")
    if start == -1:
        start = text.find("[")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    end = -1
    for i in range(start, len(text)):
        ch = text[i]
        if esc: esc = False; continue
        if ch == "\\": esc = True; continue
        if ch == '"': in_str = not in_str; continue
        if in_str: continue
        if ch in "{[": depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0: end = i + 1; break
    if end == -1:
        return None
    try:
        s = text[start:end]
        s = re.sub(r",\s*}", "}", s)
        s = re.sub(r",\s*\]", "]", s)
        return json.loads(s)
    except json.JSONDecodeError:
        return None
