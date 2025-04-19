import requests
import json
from queue import Queue

class DeepSeekLLM:
    MODEL_MAP = {
        'v3': 'deepseek-chat',
        'r1': 'deepseek-reasoner'
    }
    
    def __init__(self, api_key: str, model: str = 'r1'):
        if model not in self.MODEL_MAP:
            raise ValueError(f"Invalid model: {model}. Choose 'r1' or 'v3'")
            
        self.api_key = api_key
        self.model = self.MODEL_MAP[model]
        self.base_url = "https://api.deepseek.com/chat/completions"
    
    def generate(self, prompt: str, queue: Queue):
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
            'Authorization': f'Bearer {self.api_key}'
        }
        
        payload = {
            "messages": [
                {"role": "system", "content": "Ты - полезный ИИ-помощник"},
                {"role": "user", "content": prompt}
            ],
            "model": self.model,
            "frequency_penalty": 0,
            "max_tokens": 2048,
            "presence_penalty": 0,
            "response_format": {"type": "text"},
            "stop": None,
            "stream": True,
            "temperature": 1.3,
            "top_p": 1,
            "tools": None,
            "tool_choice": "none",
            "logprobs": False,
            "top_logprobs": None
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                stream=True
            )
            
            if response.status_code != 200:
                queue.put({'type': 'error', 'data': f"API Error: {response.status_code}"})
                return

            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    
                    if decoded_line.startswith('data: '):
                        event_data = decoded_line[6:].strip()
                        
                        if event_data == '[DONE]':
                            queue.put({'type': 'end'})
                            return
                        
                        try:
                            data = json.loads(event_data)
                            if 'choices' not in data:
                                continue
                                
                            delta = data['choices'][0].get('delta', {})
                            content = delta.get('content', '')
                            reasoning_content = delta.get('reasoning_content', '')
                            
                            if content:
                                queue.put({'type': 'content', 'data': content})
                            
                            if reasoning_content:
                                queue.put({'type': 'reasoning', 'data': reasoning_content})
                                
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            queue.put({'type': 'error', 'data': str(e)})
        finally:
            queue.put({'type': 'end'})
class LocalLLM:
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url.rstrip("/")
    
    def generate(self, prompt: str, queue: Queue):
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": "current",
            "messages": [
                {"role": "system", "content": "Ты — локальный LLM‑сервер"},
                {"role": "user",   "content": prompt}
            ],
            "stream": True
        }
        try:
            resp = requests.post(
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
                stream=True
            )
            if resp.status_code != 200:
                queue.put({'type':'error','data':f"Server error: {resp.status_code}"})
                return
            for line in resp.iter_lines():
                if not line: continue
                text = line.decode().lstrip("data: ").strip()
                if text == "[DONE]":
                    queue.put({'type':'end'})
                    return
                data = json.loads(text)
                delta = data['choices'][0].get('delta', {})
                content = delta.get('content', "")
                if content:
                    queue.put({'type':'content','data':content})
        except Exception as e:
            queue.put({'type':'error','data':str(e)})
        finally:
            queue.put({'type':'end'})