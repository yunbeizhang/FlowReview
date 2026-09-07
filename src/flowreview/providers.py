"""Model requests for OpenAI, Anthropic and Bedrock."""
from dataclasses import dataclass
import json
import os
import time
import uuid
import httpx
from . import protocol


def openai_messages(system, messages):
    output = [{"role": "system", "content": system}] if system else []
    for message in messages:
        blocks = message["content"]
        texts = [b["text"] for b in blocks if "text" in b]
        uses = [b["toolUse"] for b in blocks if "toolUse" in b]
        results = [b["toolResult"] for b in blocks if "toolResult" in b]
        if texts or uses:
            item = {"role": message["role"], "content": "\n".join(texts) or None}
            if uses:
                item["tool_calls"] = [{"id": u["toolUseId"], "type": "function", "function": {
                    "name": u["name"], "arguments": json.dumps(u["input"])}} for u in uses]
            output.append(item)
        for result in results:
            output.append({"role": "tool", "tool_call_id": result["toolUseId"],
                           "content": "\n".join(b.get("text", json.dumps(b.get("json", {})))
                                                for b in result["content"])})
    return output


def openai_tools(specs):
    return [{"type": "function", "function": {"name": s["toolSpec"]["name"],
             "description": s["toolSpec"].get("description", ""),
             "parameters": s["toolSpec"]["inputSchema"]["json"]}} for s in specs]


def from_openai(data):
    choice = data["choices"][0]
    item = choice["message"]
    blocks = []
    if item.get("content"):
        blocks.append({"text": item["content"]})
    for call in item.get("tool_calls") or []:
        # Invalid tool JSON is an unsuccessful response, never silently repaired.
        blocks.append({"toolUse": {"toolUseId": call["id"], "name": call["function"]["name"],
                                   "input": json.loads(call["function"]["arguments"])}})
    reason = {"stop": "end_turn", "tool_calls": "tool_use", "length": "max_tokens"}.get(
        choice.get("finish_reason"), choice.get("finish_reason"))
    return {"output": {"message": {"role": "assistant", "content": blocks}},
            "stopReason": reason, "usage": data.get("usage", {})}


def anthropic_messages(messages):
    output = []
    for message in messages:
        blocks = []
        for block in message['content']:
            if 'text' in block:
                if block['text']:
                    blocks.append({'type': 'text', 'text': block['text']})
            elif 'toolUse' in block:
                use = block['toolUse']
                blocks.append({'type': 'tool_use', 'id': use['toolUseId'],
                               'name': use['name'], 'input': use['input']})
            elif 'toolResult' in block:
                result = block['toolResult']
                content = [{'type': 'text', 'text': b['text'] if 'text' in b else json.dumps(b.get('json', {}))}
                           for b in result['content']]
                blocks.append({'type': 'tool_result', 'tool_use_id': result['toolUseId'],
                               'content': content, 'is_error': result.get('status') == 'error'})
            elif 'anthropicBlock' in block:
                blocks.append(block['anthropicBlock'])
        if blocks:
            output.append({'role': message['role'], 'content': blocks})
    return output


def from_anthropic(data):
    blocks = []
    for block in data['content']:
        if block['type'] == 'text':
            blocks.append({'text': block['text']})
        elif block['type'] == 'tool_use':
            blocks.append({'toolUse': {'toolUseId': block['id'], 'name': block['name'], 'input': block['input']}})
        elif block['type'] in ('thinking', 'redacted_thinking'):
            blocks.append({'anthropicBlock': block})
    usage = data.get('usage', {})
    return {'output': {'message': {'role': 'assistant', 'content': blocks}},
            'stopReason': data.get('stop_reason'),
            'usage': {'inputTokens': usage.get('input_tokens', 0), 'outputTokens': usage.get('output_tokens', 0)}}


@dataclass
class Route:
    provider: str = "openai"
    model: str = ""
    base_url: str = ""
    api_key_env: str = ""
    region: str = "us-east-1"
    token_parameter: str = "max_completion_tokens"
    temperature: float | None = None

    def __post_init__(self):
        if not self.base_url:
            self.base_url = 'https://api.anthropic.com/v1' if self.provider == 'anthropic' else 'https://api.openai.com/v1'
        if not self.api_key_env:
            self.api_key_env = 'ANTHROPIC_API_KEY' if self.provider == 'anthropic' else 'OPENAI_API_KEY'


class Provider:
    def __init__(self, route, writer=None, routes=None, timeout=120, retries=2):
        self.route = route
        self.routes = routes or {}
        self.writer = writer
        self.timeout = timeout
        self.retries = retries
        self.calls = 0
        self.errors = 0
        self.client = httpx.Client(timeout=timeout)
        self.bedrock_clients = {}

    def close(self):
        self.client.close()
        for client in self.bedrock_clients.values():
            client.close()

    def request(self, route, system, messages, max_tokens, specs):
        if route.provider == "openai":
            key = os.environ.get(route.api_key_env)
            if not key:
                raise ValueError(f"Set {route.api_key_env} (use a dummy value for an unauthenticated local server)")
            body = {"model": route.model, "messages": openai_messages(system, messages),
                    route.token_parameter: max_tokens}
            if route.temperature is not None:
                body["temperature"] = route.temperature
            if specs:
                body["tools"] = openai_tools(specs)
            response = self.client.post(route.base_url.rstrip("/") + "/chat/completions",
                                        headers={"Authorization": "Bearer " + key}, json=body)
            response.raise_for_status()
            return from_openai(response.json())
        if route.provider == 'anthropic':
            key = os.environ.get(route.api_key_env)
            if not key:
                raise ValueError(f'Set {route.api_key_env}')
            body = {'model': route.model, 'messages': anthropic_messages(messages), 'max_tokens': max_tokens}
            if system:
                body['system'] = system
            if route.temperature is not None:
                body['temperature'] = route.temperature
            if specs:
                body['tools'] = [{'name': s['toolSpec']['name'],
                                  'description': s['toolSpec'].get('description', ''),
                                  'input_schema': s['toolSpec']['inputSchema']['json']} for s in specs]
            response = self.client.post(route.base_url.rstrip('/') + '/messages',
                                        headers={'x-api-key': key, 'anthropic-version': '2023-06-01'}, json=body)
            response.raise_for_status()
            return from_anthropic(response.json())
        if route.provider == "bedrock":
            import boto3
            from botocore.config import Config
            if route.region not in self.bedrock_clients:
                self.bedrock_clients[route.region] = boto3.client("bedrock-runtime", region_name=route.region,
                    config=Config(read_timeout=self.timeout, retries={"total_max_attempts": 1}))
            body = {"modelId": route.model, "messages": messages,
                    "inferenceConfig": {"maxTokens": max_tokens}}
            if system:
                body["system"] = [{"text": system}]
            if route.temperature is not None:
                body["inferenceConfig"]["temperature"] = route.temperature
            if specs:
                body["toolConfig"] = {"tools": specs}
            return self.bedrock_clients[route.region].converse(**body)
        raise ValueError(f"Unknown provider: {route.provider}")

    def call(self, alias, messages, system, tags, max_tokens=1200, tool_specs=None, fixture=None):
        route = self.routes.get(alias, self.route)
        started = time.monotonic()
        ids = []
        raw = None
        failure = None
        for attempt in range(self.retries + 1):
            ids.append(uuid.uuid4().hex)
            self.calls += 1
            try:
                if route.provider == "mock":
                    if fixture is None:
                        raise ValueError("This suite has no mock fixture")
                    raw = {"output": {"message": {"role": "assistant", "content": [
                        {"text": protocol.canonical(fixture)}]}}, "stopReason": "end_turn", "usage": {}}
                else:
                    raw = self.request(route, system, messages, max_tokens, tool_specs)
                failure = None
                break
            except Exception as exc:
                status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                code = getattr(exc, "response", {}).get("Error", {}).get("Code") if isinstance(getattr(exc, "response", None), dict) else None
                # Do not log raw HTTP responses, URLs, headers or exception text containing secrets.
                failure = {"type": type(exc).__name__, "http_status": status, "service_code": code}
                retryable = isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)) or status in (408, 429, 500, 502, 503, 504) or code in ("ThrottlingException", "ServiceUnavailableException", "ModelTimeoutException")
                if not retryable or attempt == self.retries:
                    break
                time.sleep(min(2 ** attempt, 8))
        if failure:
            self.errors += 1
        raw = raw or {"output": {"message": {"role": "assistant", "content": []}}, "stopReason": "provider_error"}
        text = "\n".join(b["text"] for b in raw["output"]["message"]["content"] if "text" in b)
        response = {"alias": alias, "model_id": route.model, "provider": route.provider,
                    "text": text, "raw_response": raw, "provider_error": failure,
                    "stop_reason": raw.get("stopReason"), "attempt_ids": ids,
                    "in_tokens": raw.get("usage", {}).get("inputTokens", raw.get("usage", {}).get("prompt_tokens", 0)),
                    "out_tokens": raw.get("usage", {}).get("outputTokens", raw.get("usage", {}).get("completion_tokens", 0)),
                    "latency_s": round(time.monotonic() - started, 4)}
        if self.writer:
            self.writer.append({"tags": tags, "system": system, "messages": messages,
                                **{k: v for k, v in response.items() if k != "raw_response"},
                                "assistant_response": raw["output"]["message"],
                                "fixture_only": route.provider == "mock"})
        return response

    def text(self, alias, system, user, tags, fixture=None, max_tokens=1200):
        # Ground-truth fixtures are supplied only to the mock backend.
        return self.call(alias, [{"role": "user", "content": [{"text": user}]}], system,
                         tags, max_tokens=max_tokens,
                         fixture=fixture if self.routes.get(alias, self.route).provider == "mock" else None)
