from agent import agent, controller_agent
from enum import StrEnum
import psutil
import ollama
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
        self.current_depth = 0
        self.hardware = hardware()
        self.host = "http://localhost:11434"
    
    #create a project with shared context
    def create_project(self):
        with open("projects/project.json", "w") as f:
            f.write("{}")
    
    #make the a controller agent with the ability to create new agents and manage them
    #the first one created (no depth given) is the root controller at max depth
    def create_controller_agent(self, depth: int | None = None):
        if depth is None:
            depth = self.max_depth
        model = self.pick_model()
        if model is None:
            raise RuntimeError("no suitable model found for controller agent")
        new_controller = controller_agent(
            session=self,
            role=f"{self.type.value}-controller",
            depth=depth,
            model=model,
            host=self.host,
        )
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
        model = self.pick_model()
        print(f"Picked model for new agent: {model}")
        if model is None:
            raise RuntimeError("no suitable model found for sub agent")
        new_agent = agent(depth=depth, model=model, role=self.type.value, host=self.host)
        self.agents.append(new_agent)
        self.current_depth += 1
        return new_agent
    

    #TODO remove this - test the agents by sending a simple request to each one 
    def test_agents(self):
        for agent in self.agents:
            response = agent.send_request("Hello from local-swarm")
            print(f"Agent response: {response}")

    def pick_model(self):
        free_gb = self.hardware.available_memory
        fits = [m for m in ollama.list().models if m.size / 1000**3 <= free_gb]
        if not fits:
            return None
        return max(fits, key=lambda m: m.size).model
        
    def session_start(self):
        return 0
    

class hardware:
    def __init__(self):
        self.available_memory = self.get_available_memory()
        self.available_cpu = self.get_available_cpu()
    def get_available_memory(self):
        # retrieve available memory in GB
        return round(psutil.virtual_memory().available / 1000**3, 2)

    def get_available_cpu(self):
        # retrieve available CPU percentage
        return psutil.cpu_percent(interval=1)
    



        

if __name__ == "__main__":
    # Example:
    #   python3 controller.py
    current_session = session(name="default", type=SwarmType.RED_TEAM, max_depth=2)
    current_session.spawn_agents_to_max_depth(branching_factor=1)
    current_session.test_agents()  # optional: requires running Ollama model

    hardware_info = hardware()
    print(f"Available Memory: {hardware_info.available_memory} GB")
    print(f"Available CPU: {hardware_info.available_cpu} %")


    
