class SwarmType(StrEnum):
    RED_TEAM = "red-team"
    RESEARCH = "research"
    WEBSITE_MAPPING = "website-mapping"
    DEVELOPER = "developer"

class session:
    def __init__(self, name: str = "default", type: SwarmType = SwarmType.RED_TEAM):
        self.agents = []
        self.name = name
        self.type = type
    
    #create a project with shared context
    def create_project(self):
        with open("projects/project.json", "w") as f:
            f.write("{}")
    
    def create_controller_agent(self):
        return 0
    
    def session_start(self):
        return 0
    
    
