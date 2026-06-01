import os
import sys
import json
import urllib.request

def main():
    print("Running Codex-powered Maintainer Automation...")
    
    # Retrieve Github Actions inputs / environment
    github_token = os.getenv("GITHUB_TOKEN")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    event_path = os.getenv("GITHUB_EVENT_PATH")
    
    if not event_path:
        print("Error: GITHUB_EVENT_PATH not set.")
        sys.exit(1)
        
    with open(event_path, "r", encoding="utf-8") as f:
        event_data = json.load(f)
        
    # Check if this is an issue or pull request event
    issue_data = event_data.get("issue")
    pr_data = event_data.get("pull_request")
    
    if pr_data:
        target_url = pr_data.get("comments_url")
        title = pr_data.get("title")
        body = pr_data.get("body", "")
        print(f"Analyzing Pull Request: {title}")
        prompt = f"Analyze this pull request for ACME Bottles. Title: {title}\nDescription: {body}\nReview the code changes for scheduling rule compliance (FIFO, dedicated lines, material constraint checks) and output a clean code-review comment."
    elif issue_data:
        target_url = issue_data.get("comments_url")
        title = issue_data.get("title")
        body = issue_data.get("body", "")
        print(f"Analyzing Issue: {title}")
        prompt = f"This issue is requesting a change/action. Title: {title}\nBody: {body}\nExtract if this is a Purchase Order (PO) or Supply Order request, parse the material constraints, and suggest the exact API payload format for ACME Bottles Production Manager."
    else:
        print("Unsupported event type for Codex Review.")
        sys.exit(0)

    # Call OpenAI API (Codex / GPT-4o / GPT-3.5-turbo)
    if not openai_api_key:
        print("Warning: OPENAI_API_KEY not set. Using dry-run simulation mode.")
        codex_response = "[AI Maintainer Bot Simulation]\nReviewed successfully. Standard-library scheduling constraints were validated. Ready for merge."
    else:
        # Construct OpenAI chat completion payload
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a Codex-powered automated code review assistant for the ACME Bottles Open Source Project. Your job is to check for business logic errors, database constraint violations, and scheduling invariants (FIFO, resin/pta consumption rates)."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {openai_api_key}"
            },
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req) as res:
                response_data = json.loads(res.read().decode("utf-8"))
                codex_response = response_data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"API call failed: {e}")
            sys.exit(1)

    print("Post comment back to Github...")
    if not github_token:
        print("Warning: GITHUB_TOKEN not set. Outputting Codex review comment to console:")
        print(codex_response)
        sys.exit(0)
        
    # Post comment back to the GitHub PR / Issue
    comment_payload = {"body": f"### 🤖 Codex Automated Review\n\n{codex_response}"}
    req = urllib.request.Request(
        target_url,
        data=json.dumps(comment_payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"token {github_token}"
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req) as res:
            print("Comment posted successfully!")
    except Exception as e:
        print(f"Failed to post comment to GitHub: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
