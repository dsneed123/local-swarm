import ollama
import sys


# main agent class for sending simple requests to Ollama
class agent:
    def __init__(self, model: str = "llama3.2", host: str = "http://localhost:11434"):
        self.model = model
        self.client = ollama.Client(host=host)

    # send a single prompt and return only the assistant text
    def send_request(self, prompt: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")

        try:
            response = self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            return response["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"chat request failed: {e}")


if __name__ == "__main__":
    # Example:
    #   python3 agent.py "Write one short sentence about local AI"
    if len(sys.argv) < 2:
        print("Usage: python3 agent.py \"your prompt\"")
        print("Example: python3 agent.py \"Hello from local-swarm\"")
        sys.exit(0)

    prompt = " ".join(sys.argv[1:]).strip()
    bot = agent()

    try:
        reply = bot.send_request(prompt)
        print(reply)
    except Exception as e:
        print(f"Request failed: {e}")
















