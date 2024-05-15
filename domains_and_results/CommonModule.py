from copy import deepcopy, copy
from typing import Any, Dict, List
from enum import Enum
import sys

###############
## CONSTANTS ##
###############
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class DecompType(Enum):
    OK = 0
    NO_APPLICABLE_METHOD = 1
    AGENDA_EMPTY = 2
    BOTH_AGENDAS_EMPTY = 3
class OpType(Enum):
    NOT_APPLICABLE = 0
    DONE = 1

DEFAULT_ACTION_COST = 1.0
LRD_ACTION_COST = 1.0

path = "/home/sshekhar/Desktop/HATPEHDA-concurrent/domains_and_results/"

#############
## CLASSES ##
#############
## Task ##
class Task:
    __ID = 0
    def __init__(self, name: str, parameters: list, is_abstract: bool, why, method_number: int, agent: str):
        self.id = Task.__ID
        Task.__ID += 1
        self.name = name
        self.parameters = parameters
        self.agent = agent

        # From which task it is decomposed, and how (number/id of method used)
        # self.why = why  # From which task it is decomposed
        self.method_number = method_number

        self.is_abstract = is_abstract

        # self.previous = None
        # self.next = []
        self.current_plan_cost = -1.0

    def assign_next_id(self):
        self.id = Task.__ID
        Task.__ID += 1
    
    def __repr__(self):
        abs_str = "A" if self.is_abstract else "P"
        return "{}-{}{}-{}{}".format(self.id, self.agent, abs_str, self.name, self.parameters)

    def show(self):
        print(self)

class AbstractTask(Task):
    def __init__(self, name: str, parameters: list, why, method_number: int, agent: str):
        super().__init__(name, parameters, True, why, method_number, agent)

    def __repr__(self):
        return "{}-{}AT-{}{}".format(self.id, self.agent, self.name, self.parameters)



## to be refined/redefine ##
class RulesForSA:
    def __init__(self, SA, rule_antecedent_consequent=None, w_state_to_keep=None):
        self.SA = SA
        self.rule_antecedent_consequent = rule_antecedent_consequent
        self.w_state_to_keep = w_state_to_keep
    
    def is_rule_antecedent_applicable(self, rule_antecedent_consequent, w_state_to_keep):
        return self.rule_antecedent_consequent(rule_antecedent_consequent, w_state_to_keep)

class Method:
    def __init__(self, AT_name, done_cond=None, pre_cond=None, decomp=None, multi_decomp=None, get_precond=None):
        self.AT_name = AT_name
        self.done_cond = done_cond
        self.pre_cond = pre_cond
        self.decomp = decomp
        self.multi_decomp = multi_decomp
        self.get_precond = get_precond

    def get_m_precond(self, state, AT):
        return self.get_precond(state, AT.agent, *AT.parameters) if self.get_precond!=None else None

    def is_done(self, state, AT):
        return self.done_cond(state, AT.agent, *AT.parameters) if self.done_cond!=None else False

    def is_applicable(self, state, AT):
        return self.pre_cond(state, AT.agent, *AT.parameters) if self.pre_cond!=None else True
    
    def get_decomp(self, state, AT):
        if self.multi_decomp==None:
            return [self.decomp(state, AT.agent, *AT.parameters)] if self.decomp!=None else [[]]
        else:
            return self.multi_decomp(state, AT.agent, *AT.parameters)
            
class PrimitiveTask(Task):
    def __init__(self, name: str, parameters: list, why, method_number: int, agent: str) -> None:
        super().__init__(name, parameters, False, why, method_number, agent)
    
    def __repr__(self):
        return "{}-{}PT-{}{}".format(self.id, self.agent, self.name, self.parameters)

class Operator:
    def __init__(self, PT_name, done_cond=None, pre_cond=None, effects=None, cost_function=None, shared_resource=None, get_effect=None):
        self.PT_name = PT_name
        self.done_cond = done_cond
        self.pre_cond = pre_cond
        self.effects = effects
        self.cost_function = cost_function
        self.shared_resource = shared_resource
        self.get_effect = get_effect

    def get_comm_act_effect(self, state, PT):
        return self.get_effect(state, PT.agent, *PT.parameters) if self.get_effect!=None else None
    
    def is_done(self, state, PT):
        return self.done_cond(state, PT.agent, *PT.parameters) if self.done_cond!=None else False

    def get_shared_resource(self, state, PT):
        return self.shared_resource(state, PT.agent, *PT.parameters) if self.shared_resource!=None else None

    def is_applicable(self, state, PT):
        return self.pre_cond(state, PT.agent, *PT.parameters) if self.pre_cond!=None else True

    def get_cost(self, state, PT):
        return self.cost_function(state, PT.agent, *PT.parameters) if self.cost_function!=None else DEFAULT_ACTION_COST

    def apply_effects(self, state, agent: str, parameters):
        if self.effects!=None:
            self.effects(state, agent, *parameters)

    def apply(self, selected_pair, agents, PT):
        state = agents.state
        
        # Check done-condition and precondition
        """
        if self.is_done(state, PT):
            print(bcolors.WARNING + " already done!" + bcolors.ENDC)
            return OpType.DONE
        if not self.is_applicable(state, PT):
            print(bcolors.WARNING + " not applicable!" + bcolors.ENDC)
            return OpType.NOT_APPLICABLE
        """

        # moreover, the agent must also be able to verify the above conditions in the world states it cannot distingusih with
        # take this out and write it in some other file
        # this check should not be part of the operator itself
        check_done_cond = True
        check_applicable_cond = True
        for possible_world in selected_pair.possible_worlds_for_h:
            possible_world_state = possible_world.state
            # Check done-condition and pre-condition
            if not self.is_done(possible_world_state, PT):
                # print(bcolors.WARNING + " already done!" + bcolors.ENDC)
                # return OpType.DONE
                check_done_cond = False
                break
        for possible_world in selected_pair.possible_worlds_for_h:
            possible_world_state = possible_world.state
            if not self.is_applicable(possible_world_state, PT):
                # print(bcolors.WARNING + " not applicable!" + bcolors.ENDC)
                # return OpType.NOT_APPLICABLE
                check_applicable_cond = False
                break
        
        # shashank - it is a quick fix (need to do it in a better way)
        if PT.agent == "H" and check_done_cond and self.is_done(state, PT):
        # if self.is_done(state, PT):
            print(bcolors.WARNING + " already done!" + bcolors.ENDC)
            return OpType.DONE
        if PT.agent == "H" and (not check_applicable_cond or not self.is_applicable(state, PT)):
        # if not self.is_applicable(state, PT):
            print(bcolors.WARNING + " not applicable!" + bcolors.ENDC)
            return OpType.NOT_APPLICABLE
        
        # shashank - it is a quick fix (need to do it in a better way)
        # if check_done_cond and self.is_done(state, PT):
        if PT.agent == "R" and self.is_done(state, PT):
            print(bcolors.WARNING + " already done!" + bcolors.ENDC)
            return OpType.DONE
        # if not check_applicable_cond or not self.is_applicable(state, PT):
        if PT.agent == "R" and not self.is_applicable(state, PT):
            print(bcolors.WARNING + " not applicable!" + bcolors.ENDC)
            return OpType.NOT_APPLICABLE

        # Compute cost
        cost = self.get_cost(state, PT)

        if PT.agent == "H":
            print("")

        # Apply effects to acting and other agent beliefs
        # NOTE: this is not the same thing as if we are maintaining which agents are co-present and which are not 
        self.apply_effects(state, PT.agent, PT.parameters)

        # also apply this effect on all possible worlds -- quick fix (we need to update it in future)
        if PT.agent == "H":
            print("\nNumber of other worlds possible (w.r.t. the human agent) = ", len(selected_pair.possible_worlds_for_h))
            print("Action H/R applied = ", PT.name, " ", PT.parameters)
            print("")
            
        for possible_world in selected_pair.possible_worlds_for_h:
            if PT.agent == "H":
                self.apply_effects(possible_world.state, PT.agent, PT.parameters)

        # if it is a communication action, remove all the states that are not consistent with
        # what is being communicated
        selected_pair_rem_worlds = []
        if("communicate" in PT.name):
            for world in selected_pair.possible_worlds_for_h:
                if (self.get_effect(world.state, PT.agent, *PT.parameters) == self.get_effect(state, PT.agent, *PT.parameters)):
                    selected_pair_rem_worlds.append(world)

            selected_pair.possible_worlds_for_h = selected_pair_rem_worlds

        shared_resource = self.get_shared_resource(state, PT)

        return cost, shared_resource

class Action(PrimitiveTask):
    def __init__(self):
        self.cost = 0.0
        self.shared_resource = ""

    def cast_PT2A(PT: PrimitiveTask, cost: float, shared_resource: str):
        """PT is modified!!"""
        PT.__class__ = Action
        PT.__init__()
        PT.cost = cost
        PT.shared_resource = shared_resource
        return PT
    
    def minimal_init(self, id, name, parameters, agent):
        super().__init__(name, parameters, None, -1, agent)
        self.id = id

    def is_idle(self):
        return self.is_passive() and "IDLE" in self.parameters
    
    def is_pass(self):
        return self.is_passive() and "PASS" in self.parameters
    
    def is_wait(self):
        return self.is_passive() and "WAIT" in self.parameters
    
    def is_wait_turn(self):
        return self.is_passive() and "WAIT_TURN" in self.parameters

    def is_passive(self):
        return self.name=="PASSIVE"

    def create_passive(agent: str, type: str):
        return Action.cast_PT2A(PrimitiveTask("PASSIVE", [type], None, 0, agent), g_wait_cost[agent], None)

    def create_passive_signal(agent: str, type: str):
        return Action.cast_PT2A(PrimitiveTask("GET_SIGNAL", [type], None, 0, agent), g_wait_cost[agent], None)
    
    def are_similar(A1, A2):
        if A1.is_passive() and A2.is_passive():
            return True
        elif A1.name==A2.name:
            if A1.parameters==A2.parameters:
                if A1.cost==A2.cost:
                    if A1.agent==A2.agent:
                        return True
        return False

    def short_str(self):
        return f"{self.agent}{self.id}"

    def __repr__(self):
        # return "{}-{}A-{}{}-{}".format(self.id, self.agent, self.name, self.parameters, self.cost)
        return "{}-{}A-{}{}".format(self.id, self.agent, self.name, self.parameters)

class Trigger:
    def __init__(self, pre_cond, decomp):
        self.pre_cond = pre_cond
        self.decomp = decomp

## State ##
class Fluent:
    def __init__(self, name, is_dyn):
        self.name = name
        self.is_dyn = is_dyn

class State:
    def __init__(self, name):
        self.__name__ = name
        self.fluents = {}

    def create_static_fluent(self, name, value):
        fluent = Fluent(name, False)
        self.fluents[name] = fluent
        setattr(self, name, value)

    def create_dyn_fluent(self, name, value):
        fluent = Fluent(name, True)
        self.fluents[name] = fluent
        setattr(self, name, value)

    def create_derived_fluent(self, name, value):
        fluent = Fluent(name, True)
        self.fluents[name] = fluent
        setattr(self, name, value)    

    def __deepcopy__(self, memo):
        cp = State(self.__name__)
        for f in self.fluents:
            cp.fluents[f] = self.fluents[f]
            if self.fluents[f].is_dyn:
                setattr(cp,f,deepcopy(getattr(self,f)))
            else:
                setattr(cp,f,getattr(self,f))
        return cp
            

## Agent ##
class Agent:
    def __init__(self, name):
        #####################
        # Static part
        self.name = name # type: str
        self.operators = {} # type: dict[str, Operator] # str=PT.name
        self.methods = {} # type: dict[str, list[Method]] # str=AT.name
        self.triggers = [] # type: list[Trigger]

        #####################
        # Dynamic part
        self.agenda = [] # type: list[Task]
        self.planned_actions = [] # type: list[Action]
    
    #####################
    # Methods/Functions -> Static
    def show_planned_actions(self):
        print("{} planned actions:".format(self.name))
        for a in self.planned_actions:
            print("\t-{}".format(a))

    #####################
    # Deepcopy 
    def __deepcopy__(self, memo):
        # Mandatory: to match the static or dynamic fields in __init__ and deepcopy 
        cp = Agent(self.name)
        #####################
        # Static part
        cp.operators = self.operators
        cp.methods = self.methods
        cp.triggers = self.triggers

        #####################
        # Dynamic part
        # cp.state = deepcopy(self.state)
        cp.agenda = copy(self.agenda)
        # cp.planned_actions = deepcopy(self.planned_actions)

        return cp

    def has_operator_for(self, PT):
        return PT.name in self.operators

    def has_method_for(self, AT):
        return AT.name in self.methods

class Agents:
    def __init__(self):
        self.agents = {} # type: dict[str, Agent]
        self.state = None

    def exist(self, name):
        return name in self.agents
    
    def create_agent(self, name):
        if not self.exist(name): 
            self.agents[name] = Agent(name)

    def __getitem__(self, subscript):
        return self.agents[subscript]

    def __setitem__(self, subscript, item):
        self.agents[subscript] = item

    def __delitem__(self, subscript):
        del self.agents[subscript]

## Refinement ##
class Decomposition:
    def __init__(self, subtasks, agenda=None):
        self.type = DecompType.OK
        self.subtasks = subtasks
        self.new_agenda = agenda
        self.PT = None if subtasks==[] else subtasks[0]
        self.next_action = None 
    
    def show(self):
        print(self)

    def __str__(self):
        dec_str = "["
        if self.type != DecompType.OK:
            dec_str += str(self.type)
        else:
            for i, task in enumerate(self.subtasks):
                dec_str += str(task)
                if i < len(self.subtasks)-1:
                    dec_str += " - "
        dec_str += "]"
        return dec_str

    def first_task_is_PT_and_has_op(self, agent_name):
        # checks if first task is primitive and has an operator
        first_task = self.subtasks[0]
        
        if first_task.is_abstract==False and g_static_agents[agent_name].has_operator_for(first_task):
            self.PT = self.subtasks[0]
            return True
        return False

    def first_task_is_PT_not_done(self, agent_name, state):
        # checks if first task is primitive, has an operator, is not done
        if self.first_task_is_PT_and_has_op(agent_name):
            op = g_static_agents[agent_name].operators[self.subtasks[0].name]
            return not op.is_done(state, self.PT)
        return False
    
    def first_task_is_PT_done(self, agent_name, state):
        # checks if first task is primitive, has an operator, is done
        if self.first_task_is_PT_and_has_op(agent_name):
            op = g_static_agents[agent_name].operators[self.subtasks[0].name]
            return op.is_done(state, self.PT)
        return False

class AppliedDecomposition(Decomposition):
    def __init__(self, new_agents):
        self.next_action = None
        self.end_agents = new_agents

    def cast_Dec(dec: Decomposition, new_agents: Agents):
        dec.__class__ = AppliedDecomposition
        dec.__init__(new_agents)
        return dec

    def __str__(self):
        dec_str = "["
        if self.type != DecompType.OK:
            dec_str += str(self.type)
        else:
            dec_str += str(self.next_action) + " | "
            for i, task in enumerate(self.subtasks[1:]):
                dec_str += str(task)
                if i < len(self.subtasks)-1:
                    dec_str += " - "
            dec_str += " | "
            for i, task in enumerate(self.new_agenda):
                dec_str += str(task)
                if i < len(self.new_agenda)-1:
                    dec_str += " - "
        dec_str += "]"
        return dec_str

class Refinement:
    def __init__(self, decomp=None):
        self.decompos = [] # type: list[Decomposition]
        if decomp!=None:
            self.decompos.append(decomp)
        
    def add(self, decomp):
        self.decompos.append(decomp)
    
    def show(self):
        print("[\n", end="")
        for decomp in self.decompos:
            print("\t{}".format(decomp))
        print("]")

    def show_next_actions(self):
        print("next actions:")
        for decomp in self.decompos:
            if decomp.PT != None:
                print("\t- {}".format(decomp.PT))
        print("")

class AppliedRefinement:
    def __init__(self, refinement, agents) -> None:
        self.applied_decomps = [] #type: List[AppliedDecomposition]
        for dec in refinement.decompos:
            new_agents = deepcopy(agents)
            self.applied_decomps.append( AppliedDecomposition.cast_Dec(dec, new_agents) )

    def show(self):
        print("[\n", end="")
        for d in self.applied_decomps:
            print("\t{}".format(d))
        print("]")


##################################
## GLOBAL VARIABLES AND SETTERS ##
##################################
g_domain_name=""
def set_domain_name(dom_name):
    global g_domain_name
    g_domain_name = dom_name
g_static_agents = Agents()
g_other_agent_name={"H":"R", "R":"H"}
g_wait_cost = {"R":0.0, "H":2.0}
g_idle_cost = {"R":0.0, "H":0.0}
g_starting_agent = "R"
def set_starting_agent(agent):
    global g_starting_agent
    g_starting_agent = agent
g_debug = False
def set_debug(val):
    global g_debug
    g_debug = val
g_compute_gui = False
def set_compute_gui(val):
    global g_compute_gui
    g_compute_gui = val
g_view_gui = False
def set_view_gui(val):
    global g_view_gui
    g_view_gui = val


###################
## INIT FUNCTION ##
###################
def declare_methods(agent, method_list):
    if not g_static_agents.exist(agent):
        g_static_agents.create_agent(agent)
    for m in method_list:
        if m.AT_name in g_static_agents[agent].methods:
            g_static_agents[agent].methods[m.AT_name].append(m) 
        else:
            g_static_agents[agent].methods[m.AT_name] = [m] 

def declare_operators(agent, op_list):
    if not g_static_agents.exist(agent):
        g_static_agents.create_agent(agent)
    for o in op_list:
        g_static_agents[agent].operators[o.PT_name] = o

def set_state(state):
    g_static_agents.state = state

def add_tasks(agent, tasks):
    if not g_static_agents.exist(agent):
        g_static_agents.create_agent(agent)

    for t in tasks:
        if t[0] in g_static_agents[agent].methods:
            g_static_agents[agent].agenda.append(AbstractTask(t[0], t[1:], None, 0, agent))
        elif t[0] in g_static_agents[agent].operators:
            g_static_agents[agent].agenda.append(PrimitiveTask(t[0], t[1:], None, 0, agent))
        else:
            raise Exception("{} isn't known by agent {}".format(t[0], agent))

def generate_begin_action():
    if g_starting_agent == "R":
        begin_agent = "H"
    elif g_starting_agent == "H":
        begin_agent = "R"
        
    begin_action = Action.cast_PT2A(PrimitiveTask("BEGIN", [], None, 0, begin_agent), 0.0, None)
    return begin_action


############
## PRINTS ##
############
# ─ ┌ ┐ ├ ┤ │ └ ┘
def show_init():
    print("┌────────────────────────────────────────────────────────────────────────┐")
    print("│ #INIT#                                                                 │")
    print("├────────────────────────────────────────────────────────────────────────┘")
    print_agendas_states(g_static_agents, with_static=True)

def str_init():
    out_str = ""
    out_str += "┌────────────────────────────────────────────────────────────────────────┐\n"
    out_str += "│ #INIT#                                                                 │\n"
    out_str += "├────────────────────────────────────────────────────────────────────────┘\n"
    out_str += str_agendas_states(g_static_agents, with_static=True)
    return out_str

def str_agents(agents):
    out_str = ""
    out_str += "┌────────────────────────────────────────────────────────────────────────┐\n"
    out_str += "│ #AGENTS#                                                               │\n"
    out_str += "├────────────────────────────────────────────────────────────────────────┘\n"
    out_str += str_agendas_states(agents)
    return out_str

def show_agents(agents):
    print("┌────────────────────────────────────────────────────────────────────────┐")
    print("│ #AGENTS#                                                               │")
    print("├────────────────────────────────────────────────────────────────────────┘")
    print_agendas_states(agents)

def str_agendas_states(agents, with_static=False):
    out_str = ""
    out_str += str_agendas(agents)
    out_str += "├─────────────────────────────────────────────────────────────────────────\n"
    out_str += "│ STATE =\n"
    out_str += str_state(agents.state, with_static=with_static)
    out_str += "└─────────────────────────────────────────────────────────────────────────\n"
    return out_str

def print_agendas_states(agents, with_static=False):
    print_agendas(agents)
    print("├─────────────────────────────────────────────────────────────────────────")
    print("│ STATE =")
    print_state(agents.state, with_static)
    print("└─────────────────────────────────────────────────────────────────────────")

def str_agendas(agents):
    out_str = ""
    out_str += str_agenda(agents["R"])
    out_str += str_agenda(agents["H"])
    return out_str

def print_agendas(agents):
    print_agenda(agents["R"])
    print_agenda(agents["H"])

def str_agenda(agent):
    out_str = ""
    out_str +=  "│ AGENDA {} =\n".format(agent.name)
    if len(agent.agenda)==0:
        out_str += "││\t*empty*\n"
    for t in agent.agenda:
        out_str += ("││\t{}\n".format(t))
    return out_str

def print_agenda(agent):
    print("│ AGENDA {} =".format(agent.name))
    if len(agent.agenda)==0:
        print("││\t*empty*")
    for t in agent.agenda:
        print("││\t-{}".format(t))

def str_state(state, indent=4, with_static=False):
    """Print each variable in state, indented by indent spaces."""
    out_str = ""
    if state != False:
        for f in state.fluents:
            if state.fluents[f].is_dyn or state.fluents[f].is_dyn==False and with_static:
                out_str += "││"
                for x in range(indent): out_str += " "
                out_str += f"{f}"
                out_str += ' = {}\n'.format(getattr(state, f))
    else:
        out_str += 'False\n'
    return out_str

# def compare_states(state, state_2, with_static=False):
#     """Print each variable in state, indented by indent spaces."""
#     if state != False and state_2 != False:
#         for f in state.fluents:
#             if state.fluents[f].is_dyn or state.fluents[f].is_dyn==False and with_static:
#                 # print (getattr(state,f) == getattr(state1,f1))
#                 if getattr(state, f) != getattr(state_2, f):
#                     return False
#         return True
#     else:
#         raise("Exception!!")

def compare_states(state, state_2, with_static=False):
    """Print each variable in state, indented by indent spaces."""
    if state != False and state_2 != False:
        for f in state.fluents:
            if state.fluents[f].is_dyn or state.fluents[f].is_dyn==False and with_static:
                # print (getattr(state,f))
                # print (getattr(state_2,f))
                data1 = getattr(state, f)
                data2 = getattr(state_2, f)
                matches = compare_data(data1, data2)
                # if getattr(state, f) != getattr(state_2, f):
                #     return False
                if not matches:
                    return False
        return True
    else:
        raise("Exception!!")

def compare_data(data1, data2):
    # Get the set of all keys from both dictionaries
    all_keys = set(data1.keys()) | set(data2.keys())

    # Iterate over each key
    for key in all_keys:
        # Check if the key exists in both dictionaries
        if key in data1 and key in data2:
            # Get the values associated with the key
            value1 = data1[key]
            value2 = data2[key]

            # Recursively sort the values if they are dictionaries
            if isinstance(value1, dict) and isinstance(value2, dict):
                value1 = sort_dict_recursive(value1)
                value2 = sort_dict_recursive(value2)

            # Compare the values
            if value1 != value2:
                return False
        else:
            # If the key doesn't exist in one of the dictionaries, return False
            return False

    # If all comparisons pass, return True
    return True

def sort_dict_recursive(data):
    # Sort the dictionary recursively
    sorted_data = {}
    for key, value in sorted(data.items()):
        if isinstance(value, dict):
            sorted_data[key] = sort_dict_recursive(value)
        elif isinstance(value, list):
            sorted_data[key] = sorted(value)
        else:
            sorted_data[key] = value
    return sorted_data

def print_state(state, indent=4, with_static=False):
    """Print each variable in state, indented by indent spaces."""
    if state != False:
        for f in state.fluents:
            if state.fluents[f].is_dyn or state.fluents[f].is_dyn==False and with_static:
                print("││", end='')
                for x in range(indent): sys.stdout.write(' ')
                sys.stdout.write(state.__name__ + '.' + f)
                print(' = {}'.format(getattr(state,f)))
                # test
                state1 = deepcopy(state)
                for f1 in state1.fluents:
                    print (getattr(state,f) == getattr(state1,f1))
    else:
        print('False')

def print_solutions(begin_action: Action):
    print("Solutions:")
    last_actions = get_last_actions(begin_action)

    plans = []

    for last_action in last_actions:
        plan=[]
        action = last_action
        while action != begin_action:
            plan.append(action)
            action = action.previous
        plans.append(plan)

    for plan in plans:
        print("\nPLAN:")
        n=0
        for x in plan:
            n-=1
            print(plan[n], end=" - ") if x!=plan[-1] else print(plan[n])


############
## HELPER ##
############

def get_last_actions(begin_action: Action):
    if begin_action.next==[]:
        return [begin_action]
    else:
        last_actions = []
        for next in begin_action.next:
            last_actions += get_last_actions(next)

        return last_actions
