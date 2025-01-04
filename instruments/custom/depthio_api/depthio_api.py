import requests
import sys
import json

API_KEY = "dk_6_1FPOY9RQe3LVyqEVCR3ojnLK6fsGsdNSCwJ-hTWLU"
BASE_URL = "https://api.trydepth.ai/chat"

def ask_repository_question(repo_name, question):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Make sure repo_name includes the github.com prefix
    if not repo_name.startswith('github.com/'):
        repo_name = f"github.com/{repo_name}"
    
    # Construct request data according to API docs
    data = {
        "messages": [{"role": "user", "content": question}],
        "model": "gpt-4o",
        "stream": False  # Use non-streaming mode for simpler response handling
    }
    
    # repo_name goes in query parameters
    params = {
        "repo_name": repo_name
    }
    
    try:
        response = requests.post(
            BASE_URL,
            headers=headers,
            params=params,
            json=data
        )
        
        # Check if we got an error response
        if response.status_code != 200:
            error_json = response.json()
            return error_json if isinstance(error_json, dict) else {"error": str(error_json)}
        
        # For successful responses, return the JSON response
        return response.json()
        
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python depthio_api.py <repo_name> <question>")
        sys.exit(1)
        
    repo_name = sys.argv[1]
    question = sys.argv[2]
    
    try:
        response = ask_repository_question(repo_name, question)
        print(json.dumps(response, indent=2))
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
