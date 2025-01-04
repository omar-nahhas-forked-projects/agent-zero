import requests
import json

API_KEY = "dk_6_1FPOY9RQe3LVyqEVCR3ojnLK6fsGsdNSCwJ-hTWLU"
BASE_URL = "https://api.trydepth.ai/chat"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

data = {
    "messages": [{"role": "user", "content": "What are the API routes?"}],
    "model": "gpt-4o"
}

response = requests.post(
    BASE_URL,
    headers=headers,
    params={"repo_name": "github.com/calcom/cal.com"},
    json=data,
    stream=True
)

print(f"Status Code: {response.status_code}")
print("\nHeaders:")
print(json.dumps(dict(response.headers), indent=2))

print("\nStreaming response:")
for line in response.iter_lines():
    if line:
        decoded_line = line.decode('utf-8')
        print(f"\nRaw line: {decoded_line}")
        if decoded_line.startswith('data: '):
            try:
                data_json = json.loads(decoded_line[6:])
                print(f"JSON data: {json.dumps(data_json, indent=2)}")
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON: {e}")
