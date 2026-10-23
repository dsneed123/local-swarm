import ollama
import sys


# main agent class for sending simple requests to Ollama
class agent:
    def __init__(self, model: str = "llama3.2", host: str = "http://localhost:11434", depth: int = 1):
        self.model = model
        self.client = ollama.Client(host=host)
        self.depth = depth

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



# controller agent that spawns sub agents through its session until depth runs out
class controller_agent(agent):
    def __init__(self, session, model: str = "llama3.2", host: str = "http://localhost:11434", depth: int = 1):
        super().__init__(model=model, host=host, depth=depth)
        self.session = session
        self.sub_agents = []

    # children with depth left are controllers so they can keep spawning
    def create_sub_agent(self):
        if self.depth <= 0:
            raise RuntimeError("max depth reached, cannot create sub agent")

        child_depth = self.depth - 1
        if child_depth > 0:
            new_agent = self.session.create_controller_agent(depth=child_depth)
        else:
            new_agent = self.session.create_agent(depth=child_depth)
        self.sub_agents.append(new_agent)
        return new_agent

    # recursively create agents until this controller branch reaches depth 0
    def create_agents_to_max_depth(self, branching_factor: int = 1):
        if branching_factor < 1:
            raise ValueError("branching_factor must be >= 1")

        created = []
        if self.depth <= 0:
            return created

        for _ in range(branching_factor):
            child = self.create_sub_agent()
            created.append(child)

            if isinstance(child, controller_agent):
                created.extend(child.create_agents_to_max_depth(branching_factor=branching_factor))

        return created

    def send_command(self):
        pass  # TODO
















