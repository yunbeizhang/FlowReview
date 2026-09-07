"""Provider-independent helpers used by the original experiment instruments."""
from pathlib import Path
import gzip
import hashlib
import json
import threading
import time


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def value_sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def extract_json(text):
    # Extract the first JSON object without repairing model output.
    cleaned = (text or "").replace("```json", "").replace("```", "")
    decoder = json.JSONDecoder()
    for index, character in enumerate(cleaned):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(cleaned[index:])
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def read(path):
    path = Path(path)
    if not path.exists() and path.with_name(path.name + ".gz").exists():
        path = path.with_name(path.name + ".gz")
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def rows(path):
    path = Path(path)
    if not path.exists() and path.with_name(path.name + ".gz").exists():
        path = path.with_name(path.name + ".gz")
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Writer:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def append(self, value):
        with self.lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(canonical(value) + "\n")


def response_parts(response):
    message = response.get("raw_response", {}).get("output", {}).get("message", {"role": "assistant", "content": []})
    text = "\n".join(block["text"] for block in message["content"] if "text" in block)
    uses = [block["toolUse"] for block in message["content"] if "toolUse" in block]
    return message, text, uses


def call_or_failure(provider, model, messages, system, tags, max_tokens=1000, tool_specs=None):
    """Adapter for the retained AgentDojo runner. Provider errors remain outcomes."""
    return provider.call(model, messages, system, tags, max_tokens=max_tokens, tool_specs=tool_specs)
