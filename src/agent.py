import ollama
import sys


# main agent class for sending simple requests to Ollama
class agent:
    def __init__(self, role: str, model: str, host: str, context: str = "", depth: int = 0):
        self.role = role
        self.model = model
        self.client = ollama.Client(host=host)
        self.depth = depth

        system = (
            f"You are the {role} agent in Local Swarm, a multi-agent system running on "
            f"local models. Complete the task you're given concisely. If you don't know "
            f"something, say so instead of guessing."
        )
        if context:
            system += f"\n\nContext:\n{context}"

        self.messages = [{"role": "system", "content": system}]

    # send a prompt, keep it in the conversation history, return the assistant text
    def send_request(self, prompt: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")

        self.messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat(model=self.model, messages=self.messages)
        except Exception as e:
            self.messages.pop()  # don't leave an unanswered prompt in history
            raise RuntimeError(f"chat request failed: {e}") from e

        reply = response["message"]["content"]
        self.messages.append({"role": "assistant", "content": reply})
        return reply


# controller agent that spawns sub agents through its session until depth runs out
class controller_agent(agent):
    def __init__(
        self,
        session,
        role: str,
        model: str,
        host: str = "http://localhost:11434",
        context: str = "",
        depth: int = 1,
    ):
        super().__init__(role=role, model=model, host=host, context=context, depth=depth)
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
            new_agent = self.session.create_agent(depth=child_depth, )
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
















