from agent import agent, controller_agent
from enum import StrEnum
import psutil

class SwarmType(StrEnum):
    RED_TEAM = "red-team"
    RESEARCH = "research"
    WEBSITE_MAPPING = "website-mapping"
    DEVELOPER = "developer"

class session:
    def __init__(self, name: str = "default", type: SwarmType = SwarmType.RED_TEAM, max_depth: int = 1):
        self.agents = []
        self.controller = None
        self.name = name
        self.type = type
        self.max_depth = max_depth
    
    #create a project with shared context
    def create_project(self):
        with open("projects/project.json", "w") as f:
            f.write("{}")
    
    #make the a controller agent with the ability to create new agents and manage them
    #the first one created (no depth given) is the root controller at max depth
    def create_controller_agent(self, depth: int | None = None):
        if depth is None:
            depth = self.max_depth
        new_controller = controller_agent(session=self, depth=depth)
        if self.controller is None:
            self.controller = new_controller
        self.agents.append(new_controller)
        return new_controller

    # convenience: create and store the root controller for this session
    def spawn_controller(self):
        if self.controller is not None:
            return self.controller
        return self.create_controller_agent(depth=self.max_depth)

    # grow an entire controller tree from the root until max depth is reached
    def spawn_agents_to_max_depth(self, branching_factor: int = 1):
        root = self.spawn_controller()
        return root.create_agents_to_max_depth(branching_factor=branching_factor)

    #spawn sub agents
    def create_agent(self, depth: int = 0):
        new_agent = agent(depth=depth)
        self.agents.append(new_agent)
        return new_agent
    

    #TODO remove this - test the agents by sending a simple request to each one 
    def test_agents(self):
        for agent in self.agents:
            response = agent.send_request("Hello from local-swarm")
            print(f"Agent response: {response}")
    
    def session_start(self):
        return 0
    

class hardware:
    def __init__(self):
        self.available_memory = self.get_available_memory()
        self.available_cpu = self.get_available_cpu()
    def get_available_memory(self):
        # retrieve available memory in MB
        return 1024 * psutil.virtual_memory().available / (1024 * 1024)

    def get_available_cpu(self):
        # retrieve available CPU percentage
        return psutil.cpu_percent(interval=1)


        

if __name__ == "__main__":
    # Example:
    #   python3 controller.py
   # current_session = session(name="default", type=SwarmType.RED_TEAM, max_depth=2)
    #current_session.spawn_agents_to_max_depth(branching_factor=1)
   # current_session.test_agents()  # optional: requires running Ollama model
    # current_session.test_agents()  # optional: requires running Ollama model

    
    
