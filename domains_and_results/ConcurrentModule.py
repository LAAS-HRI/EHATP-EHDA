from typing import Any, Dict, List, Tuple
from copy import deepcopy, copy
import CommonModule as CM
from anytree import RenderTree, NodeMixin
import pickle
import dill
import logging as lg
import logging.config
import sys
from progress.bar import IncrementalBar
from statistics import mean
import numpy as np
import concurrent.futures
import time
import graphviz
import simplexml

import re


logging.config.fileConfig(CM.path + 'log.conf')

import pstats

max_number_of_worlds_evaluated = 0


#############
## CLASSES ##
#############
class ActionPair:
    def __init__(self, human_action: CM.Action, robot_action: CM.Action, end_agents: CM.Agents, input_possible_worlds_for_h):
        self.human_action = human_action    #type: CM.Action
        self.robot_action = robot_action    #type: CM.Action
        self.previous = None                #type: ActionPair | None
        self.next = []                      #type: List[ActionPair]
        
        self.end_agents = end_agents        #type: CM.Agents

        # for simplicity we assume it is empty in the beginning
        self.possible_worlds_for_h = input_possible_worlds_for_h #type Set:{CM.Agents}

        self.in_human_option = None         #type: HumanOption | None

        # shashank
        self.node_type = None
        self.node_done = None
        self.node_pass = None
        self.copresence = False

        # OLD #
        self.best_rank_r = None
        self.best_rank_h = None
        # Only for leaf pairs
        # self.branch_metrics = None
        # self.branch_rank_r = None
        # self.branch_rank_h = None

        # NEW # Always same attributes
        # self.best_rank = None # r rank
        # self.branch_metrics = None # if != None then it is final pair

    def set_it_as_and_node(self, node_t):
        self.node_type = node_t
        
    def is_it_an_and_node(self) -> bool:
        if(self.node_type == "AND"):
            return True
        else:
            return False
    
    def set_it_done(self, node_done):
        self.node_done = node_done
        
    def is_it_an_and_node(self) -> bool:
        if(self.node_type == "DONE"):
            return True
        else:
            return False
    
    def is_passive(self) -> bool:
        return self.human_action.is_passive() and self.robot_action.is_passive()
    
    def is_begin(self) -> bool:
        return self.is_passive() and self.human_action.parameters[0]=="BEGIN" and self.robot_action.parameters[0]=="BEGIN"
    
    def is_final(self) -> bool:
        if self.human_action.is_idle() and self.robot_action.is_idle():
            return True
        if self.human_action.is_wait_turn() and self.robot_action.is_idle():
            if self.previous.human_action.is_idle() and self.previous.robot_action.is_wait_turn():
                return True
        if self.human_action.is_idle() and self.robot_action.is_wait_turn():
            if self.previous.human_action.is_wait_turn() and self.previous.robot_action.is_idle():
                return True
        return False

    def get_short_str(self) -> str:
        return f"{self.human_action.short_str()}{self.robot_action.short_str()}"

    def get_in_step(self):
        return self.in_human_option.in_step

    def __repr__(self):
        return f"H{self.human_action.id}-{self.human_action.name}{self.human_action.parameters}|R{self.robot_action.id}-{self.robot_action.name}{self.robot_action.parameters}"

class HumanOption:
    def __init__(self, pairs: List[ActionPair]):
        self.action_pairs = pairs                   #type: List[ActionPair]
        self.in_step = None                         #type: Step | None
        self.human_action = pairs[0].human_action   #type: CM.Action
        self.robot_actions = []                     #type: List[CM.Action]
        self.best_robot_pair = None
        self.best_human_pair = None
        # inits
        for p in pairs:
            self.robot_actions.append(p.robot_action)
            p.in_human_option = self
        self.robot_choice = None

    def add_robot_passive(self, type):
        # If robot already has a passive action, add type in params
        result = check_list(self.robot_actions, lambda ra: ra.is_passive())
        if result!=None:
            result.parameters += [type]
        
        # If no passive action, create it
        else:
            passive_action = CM.Action.create_passive("R", type)
            self.robot_actions.append(passive_action)
            selected_pair = self.in_step.from_pair
            new_agents = get_agents_after_action(selected_pair.end_agents, self.human_action)
            passive_pair = ActionPair(self.human_action, passive_action, new_agents)
            passive_pair.in_human_option = self
            passive_pair.previous = selected_pair
            selected_pair.next.append(passive_pair)
            self.action_pairs.append(passive_pair)

    def get_str(self):
        # ─ ┌ ┐ ├ ┤ │ └ ┘
        human_action_name = self.human_action.name if self.human_action.name!="PASSIVE" else "P"
        str_h = f"┌H{self.human_action.id}-{human_action_name}{self.human_action.parameters}┐"
        str_r = "│"
        sra_present = False
        for i, ra in enumerate(self.robot_actions):
            robot_action_name = ra.name if ra.name!="PASSIVE" else "P"
            str_r += f"R{ra.id}-{robot_action_name}{ra.parameters}│"

        l_h = len(str_h)
        l_r = len(str_r)

        if l_h<l_r:
            diff = l_r-l_h
            padding = ""
            for i in range(int(diff/2)):
                padding+="─"
            
            str_h = str_h[1:-1]
            if diff%2==1:
                str_h = "┌" + padding + str_h + padding + "─┐"
            else:
                str_h = "┌" + padding + str_h + padding + "┐"
        elif l_h>l_r:
            str_r = str_r[:-1]
            diff = l_h-l_r
            padding_f = ""
            for i in range(diff//2):
                padding_f+=" "
            padding_e = ""
            for i in range(diff-diff//2):
                padding_e+=" "
            str_r = str_r[0] + padding_f + str_r[1:] + padding_e + "│"

        l_end = max(len(str_h), len(str_r))-2
        str_end = ""
        for i in range(l_end):
            str_end+="─"
        str_end = "└" + str_end + "┘"

        return str_h, str_r, str_end
        
    def show(self):
        str_1, str_2, str_3 = self.get_str()
        print(str_1)
        print(str_2)
        print(str_3)

G_CRITERIA = None
class BaseStep:
    __ID = 0 #type: int
    

    def __init__(self):
        self.id = BaseStep.__ID
        BaseStep.__ID += 1
        self.human_options = []  #type: List[HumanOption]
        self.best_robot_pair = None
        self.best_human_pair = None
        self.CRA = []                       #type: List[CM.Action] # Common Robot Actions
        self.from_pair = None

    def init(self, human_options: List[HumanOption], from_pair: ActionPair):
        self.human_options = human_options  #type: List[HumanOption]
        self.from_pair = from_pair
        # inits
        for ho in human_options:
            ho.in_step = self
        # Set next/previous of each pairs from new_step
        # Connect new pairs and expanded/select pair
        if from_pair!=None:
            all_step_pairs = self.get_pairs()
            from_pair.next += all_step_pairs
            for p in all_step_pairs:
                p.previous = from_pair
                if from_pair.node_type == "AND":
                    p.node_type = "OR"
                else:
                    p.node_type = "AND"

        
    def isRInactive(self):
        for p in self.get_pairs():
            if not p.robot_action.is_passive():
                return False
        return True
    
    def isHInactive(self):
        for p in self.get_pairs():
            if not p.human_action.is_passive():
                return False
        return True

    def is_passive(self):
        return self.isRInactive() and self.isHInactive()
    
    def is_final(self):
        pairs = self.get_pairs()
        if len(pairs)==1:
            if pairs[0].is_final():
                return True
        return False

    def __lt__(self, other):
        return compare_metrics(self.get_f_leaf().branch_metrics, other.get_f_leaf().branch_metrics, G_CRITERIA)

    def get_nb_states(self):
        begin_pair = self.get_pairs()[0]
        return self.rec_get_nb_states(begin_pair)

    def rec_get_nb_states(self, p : ActionPair):
        nb_state = 1
        for c in p.next:
            nb_state += self.rec_get_nb_states(c)
        return nb_state

    def get_f_leaf(self):
        if not self.is_final():
            raise Exception("Not a final step!")
        return self.get_pairs()[0]
    
    def get_pairs(self) -> List[ActionPair]:
        pairs = [] #type: List[ActionPair]
        for ha in self.human_options:
            pairs += ha.action_pairs
        return pairs

    def get_final_leaves(self, tt_explore=False):
        leaves = []
        for leaf in self.leaves:
            if leaf.is_final():
                leaves.append(leaf)
        return leaves

    def show(self, last_line=True):
        a_from = "" if self.from_pair==None else f"-{self.from_pair.get_short_str()}"
        print(f"========= Step{self}{a_from} =========")
        ho_l1, ho_l2, ho_l3 = [], [], []
        for ho in self.human_options:
            l1, l2, l3 = ho.get_str()
            ho_l1.append(l1)
            ho_l2.append(l2)
            ho_l3.append(l3)
        str_1, str_2, str_3 = "", "", ""
        for i in range(len(self.human_options)):
            str_1 += ho_l1[i] + " "
            str_2 += ho_l2[i] + " "
            str_3 += ho_l3[i] + " "
        print(str_1)
        print(str_2)
        print(str_3)
        if last_line:
            print(f"===============================")

    def str(self, last_line=True):
        out_str = ""
        a_from = "" if self.from_pair==None else f"-{self.from_pair.get_short_str()}"
        out_str += f"========= Step{self}{a_from} =========\n"
        ho_l1, ho_l2, ho_l3 = [], [], []
        for ho in self.human_options:
            l1, l2, l3 = ho.get_str()
            ho_l1.append(l1)
            ho_l2.append(l2)
            ho_l3.append(l3)
        str_1, str_2, str_3 = "", "", ""
        for i in range(len(self.human_options)):
            str_1 += ho_l1[i] + " "
            str_2 += ho_l2[i] + " "
            str_3 += ho_l3[i] + " "
        out_str += str_1+"\n"
        out_str += str_2+"\n"
        out_str += str_3+"\n"
        if last_line:
            out_str += f"===============================\n"
        return out_str


    def get_str(self, with_bold=True):
        start_flags = ""
        end_flags = ""
        if self.is_final() and with_bold:
            # start_flags = CM.bcolors.BOLD + CM.bcolors.OKBLUE
            # end_flags = CM.bcolors.ENDC
            start_flags = "#"
            end_flags = "#"
        return start_flags + f"({self.id})" + end_flags

    def __repr__(self) -> str:
        return self.get_str()

class Step(BaseStep, NodeMixin):  # Add Node feature
    def __init__(self, *params, parent=None, children=None):
        super(Step, self).__init__(*params)
        self.parent = parent
        if children:
            self.children = children

def simplify_solution(s: Step):
    # simplify step
    for p in s.get_pairs():
        p.end_agents = None

    # base case
    if s.children==[]:
        return

    # recursion
    for c in s.children:
        simplify_solution(c)

#############
## EXPLORE ##
#############
def explore(tt_explore = False, allowed_to_signal = False, goal_test = [False, ""]):
    # lg.info(CM.str_init())

    # Generate initial step
    # init agents
    initial_agents = deepcopy(CM.g_static_agents)

    # if we need to signal apart from communication
    # allowed_to_signal = False

    # lets start with a fix designated world

    # initial_world_uncertainty = {initial_agents : "real world"}
    # the idea is to maintain possibe worlds that do not exist in reality however the human cannot differentiate 
    # them with the real designated world -- I.e. initial/end_agent 
    initial_possible_worlds_for_h = []

    # init ActionPair
    begin_action_R = CM.Action.create_passive("R", "BEGIN")
    begin_action_H = CM.Action.create_passive("H", "BEGIN")
    init_pair = ActionPair(begin_action_H, begin_action_R, initial_agents, initial_possible_worlds_for_h)
    
    # shashank for the AND-OR search
    if(CM.g_starting_agent == "H"):
        init_pair.set_it_as_and_node("AND")
        init_pair.set_it_done("NOT_DONE")
    else:
        init_pair.set_it_as_and_node("OR")
        init_pair.set_it_done("NOT_DONE")

    # init HOption
    init_h_option = HumanOption([init_pair])
    # init Step
    init_step = Step()
    init_step.init([init_h_option], None)
    init_step.CRA = begin_action_R
    lg.debug(f"{init_step.str()}")

    # Several exploration steps
    MULTI_THREADING = False
    if  MULTI_THREADING:
        e = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        pairs_to_explore = [init_pair]
        e.submit(recursive_loop_explo_para, e, pairs_to_explore)
        e.shutdown(wait=True)
        print("done")
    else:
        pairs_to_explore = [] # order=priority
        pairs_to_explore.append(init_pair)
        bar = IncrementalBar("Exploring", max=len(pairs_to_explore), width=60, suffix='%(index)d/%(max)d - %(elapsed_td)s')

        ## need to understand this
        # already_explored = []
        while pairs_to_explore != []:
            lg.debug(f"\nNEW STEP:\npairs to explore:\n\t{pairs_to_explore}")
            if tt_explore:
                pairs_to_explore = exploration_step_tt(pairs_to_explore, allowed_to_signal, goal_test)                
            else:
                pairs_to_explore = exploration_step(pairs_to_explore)
            lg.debug(RenderTree(init_step))
            
            # progress bar #
            bar.max = max(bar.max, len(pairs_to_explore))
            bar.goto(len(pairs_to_explore))
            ##########
        bar.finish()

        global max_number_of_worlds_evaluated
        print("maximum numbers of world evaluated: " + str(max_number_of_worlds_evaluated))

    # print(f"Number of leaves: {len(init_step.get_final_leaves())}")

    compute_metrics(init_step.get_final_leaves())

    return init_step

################################
## EXPLORE for an AND/OR TREE ##
################################
def explore_ANDOR(tt_explore = False, allowed_to_signal = False, goal_test = []):
    
    goal_test = [False, ""]

    # lg.info(CM.str_init())

    # Generate initial step
    # init agents
    initial_agents = deepcopy(CM.g_static_agents)      

    # the idea is to maintain possibe worlds that do not exist in reality however the human cannot differentiate 
    # them with the real designated world -- I.e. initial/end_agent 
    initial_possible_worlds_for_h = []

    # init ActionPair
    begin_action_R = CM.Action.create_passive("R", "BEGIN")
    begin_action_H = CM.Action.create_passive("H", "BEGIN")
    init_pair = ActionPair(begin_action_H, begin_action_R, initial_agents, initial_possible_worlds_for_h)
    
    # shashank for the AND-OR search
    if(CM.g_starting_agent == "H"):
        init_pair.set_it_as_and_node("AND")
        init_pair.set_it_done("NOT_DONE")
    else:
        init_pair.set_it_as_and_node("OR")
        init_pair.set_it_done("NOT_DONE")

    # init HOption
    init_h_option = HumanOption([init_pair])
    # init Step
    init_step = Step()
    init_step.init([init_h_option], None)
    init_step.CRA = begin_action_R
    lg.debug(f"{init_step.str()}")

    # Several exploration steps
    MULTI_THREADING = False
    if  MULTI_THREADING:
        e = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        pairs_to_explore = [init_pair]
        e.submit(recursive_loop_explo_para, e, pairs_to_explore)
        e.shutdown(wait=True)
        print("done")
    else:               
        pairs_to_explore = [] # order=priority
        pairs_to_explore.append(init_pair)

        # NOTE: for now allowing the robot to choose PASS first when using AND/OR search will not work
        fun_AND_OR_search_new(pairs_to_explore, allowed_to_signal, goal_test)
        # fun_AND_OR_search(pairs_to_explore, allowed_to_signal, goal_test)

        # if(pairs_to_explore[0].node_done != "DONE"):
        #     print("ERROR!!")

    # print(f"Number of leaves: {len(init_step.get_final_leaves())}")   

    compute_metrics(init_step.get_final_leaves())    

    extract_complete_andor_policy (init_step)

    return init_step

# extract policy:
def extract_complete_andor_policy(init_step):
    if init_step.from_pair != None or init_step.depth == 0:
        policy = init_step.from_pair
        if policy == None:
            print()
        if policy == None and init_step.depth == 0:   
            extract_complete_andor_policy(init_step.children[0])
            return 
        if policy.node_type == "AND":
            children = []
            for child in init_step.children:
                if child.from_pair.node_done == "DONE":
                    children.append(child)
                    extract_complete_andor_policy(child)
            init_step.children = children
        elif policy.node_type == "OR":
            children = []
            for child in init_step.children:
                if child.from_pair.node_done == "DONE":
                    children.append(child)
                    extract_complete_andor_policy(child)
                    break
            init_step.children = children
        
        return init_step
    

##############
def is_goal_node(pair_to_explore, allowed_to_signal):
    children = exploration_step_tt(pair_to_explore, allowed_to_signal) 
    if children == []:
        return True
    else:
        return False

def is_leaf_node(pair_to_explore, allowed_to_signal):
    return False


def is_root_solved(root):
    if root.node_done == "DONE":
        return True
    return False


def regress_new_status_backward(element):
    if element.node_done == "DONE" or element.node_pass == "pass":
        parent = element.previous
        if parent.node_done == "DONE":
            return
        while parent != None:
            if(parent.node_type == "OR"):
                for child in parent.next:
                    if child.node_pass == "pass":
                        continue
                    if child.node_done == "DONE":
                        parent.node_done = "DONE"
                        break
                if parent.previous != None:
                    parent = parent.previous    
                    if parent.node_done == "DONE":
                        return     
                else:
                    return
            elif(parent.node_type == "AND"):
                for child in parent.next:
                    if child.node_pass == "pass":
                        continue
                    if child.node_done != "DONE":
                        return
                # if len(parent.next) > 1:
                parent.node_done = "DONE"
                # else:
                #     parent.node_pass = "pass"
                if parent.previous != None:
                    parent = parent.previous
                    if parent.node_done == "DONE":
                        return       
                else:
                    return

# NOTE: for now allowing the robot to choose PASS first when using AND/OR search will not work
# currently it does not allow to find a solution in a breadth-first search manner 
def fun_AND_OR_search_new(pair_to_explore, allowed_to_signal, goal_test):
    # pair_to_explore: it is the initial pair we begin with
    root = pair_to_explore
    # explored = []
    frontier = [] 
    frontier.append(root[0])
    while frontier != []:
        element = frontier.pop(0)
        # explored += [element]
        element_copy = deepcopy(element)
        # forward search
        children = exploration_step_tt([element], allowed_to_signal, goal_test)          

        if children == []:
            goal_test[0] = True      
            # if we can save things here
            verify_cycle([element_copy], allowed_to_signal, goal_test)
            # if goal_test[1] == "goal" or goal_test[1] == "pass":
            if goal_test[1] == "goal":
                element.node_done = "DONE"
            elif goal_test[1] == "pass":
                element.node_pass = "pass"
                
            # backward search: update solved node  
            regress_new_status_backward(element) 
            print() 
        if is_root_solved(root[0]):
            break
        frontier = frontier + children
        # frontier = children + frontier 
    ##############
    global max_number_of_worlds_evaluated
    print("maximum numbers of world evaluated: " + str(max_number_of_worlds_evaluated))
    
    
# NOTE: for now allowing the robot to choose PASS first when using AND/OR search will not work
# currently it does not allow to find a solution in a breadth-first search manner 
def fun_AND_OR_search(pair_to_explore, allowed_to_signal, goal_test):
    pair_to_explore_loc = deepcopy(pair_to_explore)    
    pair_to_explore_goal_test = deepcopy(pair_to_explore)    
    goal_test = [False, ""]
    children = exploration_step_tt(pair_to_explore, allowed_to_signal, goal_test) 
    if children == []:  
        goal_test[0] = True      
        verify_cycle(pair_to_explore_goal_test, allowed_to_signal, goal_test)
        return goal_test 
    elif pair_to_explore_loc[0].node_type == "OR":
        for child in children:
            goal_test = [False, ""]
            goal_test = fun_AND_OR_search([child], allowed_to_signal, goal_test)
            if goal_test[1] == "goal":
                return [False, "goal"]
            elif goal_test[1] == "pass":
                continue
        return False
    elif pair_to_explore_loc[0].node_type == "AND":
        for child in children:
            goal_test = [False, ""]
            goal_test = fun_AND_OR_search([child], allowed_to_signal, goal_test)
            if goal_test[1] == "pass":
                continue
            if not goal_test[1] == "goal":
                return [False, ""]
        return [False, "goal"]
##############

def verify_cycle(pair_to_explore, allowed_to_signal, goal_test):
    return exploration_step_tt(pair_to_explore, allowed_to_signal, goal_test)

#####################
## MULTI_THREADING ##
#####################
def recursive_loop_explo_para(e: concurrent.futures.ThreadPoolExecutor, pairs_to_explore: List[ActionPair]):
    jobs = [] # type: List[concurrent.futures.Future]
    for p in pairs_to_explore:
        jobs.append(e.submit(new_exploration_step, p))

    i = 0
    while jobs!=[]:
        if jobs[i].done():
            job = jobs.pop(i)
            e.submit(recursive_loop_explo_para, e, job.result())
        else:
            i = i+1 if i+1<len(jobs) else 0
        time.sleep(0.01)    

def new_exploration_step(selected_pair):
    parallel_pairs = compute_parallel_pairs(selected_pair)
    human_options = arrange_pairs_in_HumanOption(parallel_pairs)
    new_step = Step(parent=selected_pair.get_in_step())
    new_step.init(human_options, selected_pair)
    new_step.CRA = identify_CRA(new_step)
    lg.info(f"{new_step.str()}")

    return new_get_pairs_to_explore(new_step)

def new_get_pairs_to_explore(new_step: Step):
    new_explo_pairs = []
    
    # add all pairs except double passive
    for pair in new_step.get_pairs():
        if not pair.is_passive():
            new_explo_pairs.append(pair)

    return new_explo_pairs

################
## EXPLO STEP ##
################
def exploration_step(pairs_to_explore):
    selected_pair = select_pair_to_explore(pairs_to_explore)
    # p = (-1,-1)
    # if selected_pair.human_action.id == p[0] and selected_pair.robot_action.id == p[1]:
    #     print("blob")
    parallel_pairs = compute_parallel_pairs(selected_pair)
    human_options = arrange_pairs_in_HumanOption(parallel_pairs)
    new_step = Step(parent=selected_pair.get_in_step())
    new_step.init(human_options, selected_pair)
    new_step.CRA = identify_CRA(new_step)
    add_systematic_r_skip(new_step, selected_pair)
    # add_robot_skips(new_step, selected_pair)
    # add_robot_leaves(new_step, selected_pair)
    lg.debug(f"{new_step.str()}")

    return get_pairs_to_explore(new_step, pairs_to_explore)


def exploration_when_HR_insame_context(selected_pair):
    """
    When agents are co-present -- it will be dealt as shown below
    
    # 1. Now human can see which action did the robot perform
    # 2. So in the designated world "end_agent" -- suppose robot has two ways r1 and r2 to decompose
    # 3. If the robot chooses r1 -- and the first action is a1 in the decomposition r1 
    # 4. create a new epistemic state, real world is the one generated post a1
    # 5. for updating/keeping the possible worlds: retain all possible worlds from "possible_worlds_for_h" in which
    # 6. at least one decomposition, e.g. r1 allows to execute a1 next in it -- it create new worlds using only those decompositions 
    """

    ## this gets us all possible designated refinements to be applied in reality
    selected_pair_loc = deepcopy(selected_pair)
    ref = get_applied_refinement("R", selected_pair, selected_pair.end_agents)
    pairs = []
    h_pass = CM.Action.create_passive("H", "WAIT_TURN")
    

    # If in reality the robot cannot act i.e. ref is None 
    # Means agents might still have to achieve the shared goal but due to lack of resources 
    # the robot cannot act at this stage -- so it has option to be PASSIVE & WAIT 
    no_next_real_action_r = False
    for dec in ref.applied_decomps:
        if dec.next_action.name == "PASSIVE" and dec.next_action.parameters[0] == "WAIT":
            no_next_real_action_r = True

    if not no_next_real_action_r:
        # when H and R are co-present, R's actions affect the beliefs of the human
        # human can deduce/infer new set of possible world, which would be subset of the possible worlds before 
        # for this deduction, human consideres all possible worlds and possible agendas
        for dec in ref.applied_decomps:  
            _after_refuting_impossible_worlds_wrt_designated_refinements = [] 
            # as per the new refinements wrt a possible world (that human is uncertain about) and robot as 
            # an acting agent
            # if there is an action in a refinement applicable in this world which is exactly what the robot 
            # applies in the designated world, then, 
            # human will still not be able to distinguish the next possible world generated with the 
            # next designated world 
            for each_possible_world in selected_pair_loc.possible_worlds_for_h:
                possible_ref = get_applied_refinement("R", selected_pair_loc, each_possible_world)
                for possible_dec in possible_ref.applied_decomps:          
                    # for now, consider their names and the parameter lists  
                    if (dec.next_action.name == possible_dec.next_action.name):
                        same_param_list = True
                        for par in range(len(dec.next_action.parameters)):
                            if dec.next_action.parameters[par] != possible_dec.next_action.parameters[par]: 
                                same_param_list = False
                        for par in range(len(possible_dec.next_action.parameters)):
                            if dec.next_action.parameters[par] != possible_dec.next_action.parameters[par]: 
                                same_param_list = False 

                        ## Robot's next designated action will be assessed by the human in the current context
                        ## It may reduce the overall uncertainty the human is carrying by seeing this action 
                        ## This is INFERENCE -- if human sees the robot taking next actions
                        ## What human does is they refers to all possible worlds (states+agendas)
                        ## Based on that, human knows for which all possible worlds robot can take this action        
                        if same_param_list:
                            _after_refuting_impossible_worlds_wrt_designated_refinements.append(possible_dec.end_agents)  

            # print("\nNumber of possible worlds as per H = ", len(_after_refuting_impossible_worlds_wrt_designated_refinements))
            pairs.append(ActionPair(h_pass, dec.next_action, dec.end_agents, _after_refuting_impossible_worlds_wrt_designated_refinements)) 
    # else:

    pass_added = False
    for p in pairs:
        if p.robot_action.is_passive():
            p.robot_action.parameters.append("PASS")
            pass_added = True
            break
    
    # do not allow PASS when human is waiting for signal
    if "GET_SIGNAL" in selected_pair.human_action.name:
        pass_added = True

    if not pass_added:
        # I have updated it:  
        # list_param = "WAIT", "PASS" signifies that nothing to do for the robot and the goal is not achieved yet.
        # whether this "selected_pair.possible_worlds_for_h" should go or not -- should retain all possible "agents" ds   
        possible_worlds_h = selected_pair_loc.possible_worlds_for_h        
        act = CM.Action.create_passive("R", "WAIT")
        act.parameters.append("PASS")
        
        pairs.append(ActionPair(h_pass, act, selected_pair_loc.end_agents, possible_worlds_h))
        # pairs.insert(0, ActionPair(h_pass, act, selected_pair_loc.end_agents, possible_worlds_h))
        
        # pairs.append(ActionPair(h_pass, CM.Action.create_passive("R", "PASS"), selected_pair_loc.end_agents, possible_worlds_h))
        # pairs.insert(0, ActionPair(h_pass, CM.Action.create_passive("R", "PASS"), selected_pair_loc.end_agents, possible_worlds_h))
    return pairs


def exploration_when_HR_not_insame_context(selected_pair):       
    # Case 1: (when H and R are not co-present) 
    # Then, foreach non-designated worlds of the selected_pair ds
    # bring all possible refinements -- updated next action, the agent agendas etc.
    # each possible refinement is the possible next world for the human as they are not co-present   
    #    

    possible_worlds_post_possible_non_designated_refinements = []
    # print("\nNumber of possible worlds as per H = ", len(selected_pair.possible_worlds_for_h))

    selected_pair_loc = deepcopy(selected_pair)

    # this portion is validated now!
    for each_possible_world in selected_pair_loc.possible_worlds_for_h:
        # for the robot to apply actions w.r.t. given possible designated world when 
        # human is not in context
        selected_pair_loc_for = deepcopy(selected_pair_loc)
        selected_pair_loc_for.possible_worlds_for_h = []
        each_possible_world_for = deepcopy(each_possible_world)

        ref = get_applied_refinement("R", selected_pair_loc_for, each_possible_world_for)
        # pairs = []
        # h_pass = CM.Action.create_passive("H", "WAIT_TURN")
    
        for dec in ref.applied_decomps:            
            # pairs.append(ActionPair(dec.next_action, r_pass, dec.end_agents, selected_pair.worlds_uncertainty))
            possible_worlds_post_possible_non_designated_refinements.append(dec.end_agents)
        
        does_robot_wait = False
        for dec in ref.applied_decomps:
            if dec.next_action.is_passive():
                does_robot_wait = True

        # and to the original world itself -- when robot does not apply an action
        if(not does_robot_wait):
            possible_worlds_post_possible_non_designated_refinements.append(each_possible_world_for)

    # now for the real/designated world -- look for all possible decompositions
    # for each possible decomposition --- give NOOP for the second agent (NOOP, act_i) -- bring the next designated world
    # Note that: even out of these real decompositions, only one decomposition will be adopted in real time by the robot
    # the others will still form state uncertainity in that plan trace: I.e., end_agent ds

    # this gets us all possible designated refinements
    selected_pair_loc.possible_worlds_for_h = []
    ref_glob = get_applied_refinement("R", selected_pair_loc, selected_pair_loc.end_agents)
    ref = deepcopy(ref_glob)
    pairs = []
    h_pass = CM.Action.create_passive("H", "WAIT_TURN")

    selected_pair_loc_another = deepcopy(selected_pair)

    # testing for passive action
    does_robot_wait = False
    for dec in ref.applied_decomps:
        if dec.next_action.is_passive():
            does_robot_wait = True

    for dec in ref.applied_decomps:            
        _worlds_from_designated_refinements_not_selected = []
        for dec1 in ref.applied_decomps:
            if dec != dec1: #there should be a better way to compare dec and dec1
                _worlds_from_designated_refinements_not_selected.append(dec1.end_agents)
        
        if not does_robot_wait:
            _worlds_from_designated_refinements_not_selected.append(selected_pair_loc_another.end_agents)

        possible_worlds_h = possible_worlds_post_possible_non_designated_refinements + _worlds_from_designated_refinements_not_selected
        pairs.append(ActionPair(h_pass, dec.next_action, dec.end_agents, possible_worlds_h))

    pass_added = False
    for p in pairs:
        if p.robot_action.is_passive():
            p.robot_action.parameters.append("PASS")
            pass_added = True
            break
    if not pass_added:
        # need to verify this! whether this "selected_pair.possible_worlds_for_h" should go or the one provided below
        _worlds_from_designated_refinements_not_selected = []

        # even if the robot is not taking an action: reason(s): it passes as it cannot act next 
        ref = deepcopy(ref_glob)
        for dec in ref.applied_decomps: 
            _worlds_from_designated_refinements_not_selected.append(dec.end_agents)

        possible_worlds_h = possible_worlds_post_possible_non_designated_refinements + _worlds_from_designated_refinements_not_selected
        pairs.append(ActionPair(h_pass, CM.Action.create_passive("R", "PASS"), selected_pair.end_agents, possible_worlds_h))
        # pairs.insert(0, ActionPair(h_pass, CM.Action.create_passive("R", "PASS"), selected_pair.end_agents, possible_worlds_h)) 
    return pairs

def update_dlgp_fact_list_GRAAL(file_path, start_text, end_text, state):
    # Read the content of the file
    with open(file_path, 'r') as file:
        lines = file.readlines()

    # Find the indices of the lines with start_text and end_text
    try:
        start_index = lines.index(start_text + '\n')
        end_index = lines.index(end_text + '\n', start_index)
    except ValueError:
        print("Start or end text not found in the file.")
        return

    new_lines = []
    for f in state.fluents:
        if f != "self_name" and (state.fluents[f].is_dyn or state.fluents[f].is_dyn==False):
            # dict = getattr(state, f)
            # print(state.color_cubes["r1"]["below"])
            # print(getattr(state, f))
            for item in getattr(state, f):
                if isinstance(getattr(state, f)[item], dict):
                    # print("yes!")
                    # print(getattr(state, f)[item])                    
                    for item1 in getattr(state, f)[item]:
                        # print(getattr(state, f)[item][item1])
                        if isinstance(getattr(state, f)[item][item1], dict):
                            # print("yes!")
                            # print(getattr(state, f)[item][item1])
                            # item1_cont = state.fluents[f][item][item1]
                            if isinstance(getattr(state, f)[item][item1], list):
                                # print("yes!")
                                if len(getattr(state, f)[item][item1]) == 0:
                                    new_lines.append(f + "(" + item + ", " + item1 + ", " + "None" + ").\n")     
                                else:
                                    new_lines.append(f + "(" + item + ", " + item1 + ", " + getattr(state, f)[item][item1][0] + ").\n")                               
                            else:
                                Exception("Cannot handle a state feature with more than 3 arguments!")

                        elif isinstance(getattr(state, f)[item][item1], list):
                            if len(getattr(state, f)[item][item1]) == 0:
                                new_lines.append(f + "(" + item + ", " + item1 + ", " + "None" + ").\n")     
                            else:
                                new_lines.append(f + "(" + item + ", " + item1 + ", " + getattr(state, f)[item][item1][0] + ").\n")
                        elif isinstance(getattr(state, f)[item][item1], str):
                            new_lines.append(f + "(" + item + ", " + item1 + ", " + getattr(state, f)[item][item1] + ").\n") 
                        elif isinstance(getattr(state, f)[item][item1], bool):
                            new_lines.append(f + "(" + item + ", " + item1 + ", " + str(getattr(state, f)[item][item1]) + ").\n") 

                elif isinstance(getattr(state, f)[item], list):
                    if len(getattr(state, f)[item][0]) == None:
                        new_lines.append(f+ "(" + item + ", " + "None" + ").\n")
                    else:
                        new_lines.append(f+ "(" + item + ", " + getattr(state, f)[item][0] + ").\n")
                elif isinstance(getattr(state, f)[item], str):
                    new_lines.append(f+ "(" + item + ", " + getattr(state, f)[item] + ").\n")
                elif isinstance(getattr(state, f)[item], bool):
                    new_lines.append(f+ "(" + item + ", " + str(getattr(state, f)[item]) + ").\n")

                # elif isinstance(getattr(state, f), list):
                #     new_lines.append(f+ "(" + getattr(state, f)[item][0] + ").\n")
                # elif isinstance(getattr(state, f), str):
                #     new_lines.append(f+ "(" + getattr(state, f)[item] + ").\n")
                # elif isinstance(getattr(state, f), bool):
                #     new_lines.append(f+ "(" + str(getattr(state, f)[item]) + ").\n")
            

    # Insert new lines between start and end
    lines = lines[:start_index + 1] + new_lines + lines[end_index:]

    # Write the modified content back to the file
    with open(file_path, 'w') as file:
        file.writelines(lines)

def custom_bool(value):
    return value.lower() == 'true'

def applyRulesToInferNewFactsFromKnownOnesGRAAL(selected_pair_sa):
    agents = selected_pair_sa.end_agents

    # path = "/home/sshekhar/Desktop/HATPEHDA-concurrent/dlgp/example.dlgp"
    std_output = bringAppropriateChangesInTheWorldGRAAL(agents.state, file_path=None)   
    agents.state = update_state_post_rules_applied(agents.state, std_output) 

    for ag_state in selected_pair_sa.possible_worlds_for_h: 
        std_output = bringAppropriateChangesInTheWorldGRAAL(ag_state.state, file_path=None) 
        ag_state.state = update_state_post_rules_applied(ag_state.state, std_output)

    return selected_pair_sa    

def update_state_post_rules_applied(state, std_output):    
    specific_line = next((line for line in std_output.split('\n') if line.strip() and "number of extra facts added" in line), None)
    match = re.search(r'.* (\d+)$', specific_line)
    integer_value = int(match.group(1))
    if integer_value == 0:
        return state
    else:
        # update the state with newly added facts in the fact base
        # 1. find out what is produced new and was not present in the previous fact base
         
        # Extract lines between markers
        facts_original_fact_base = extract_lines_between_markers(std_output, "print fact-base", "updated fact-base after applying the rules")
        facts_in_updated_fact_base = extract_lines_between_markers(std_output, "updated fact-base after applying the rules", "number of extra facts added")

        # Print the extracted lines for verification
        # print("Lines between 'print fact-base' and 'updated fact-base after applying the rules':")
        # print(facts_original_fact_base)

        # print("\nLines between 'updated fact-base after applying the rules' and 'number of extra facts added':")
        # print(facts_in_updated_fact_base)

        extra_lines = find_extra_facts_added(facts_original_fact_base, facts_in_updated_fact_base)

        for line in extra_lines:
        # for line in facts_in_updated_fact_base:
            words_list = split_line_and_filter(line)
            size = len(words_list) - 2
            if size==2:
                if isinstance(getattr(state, words_list[0])[words_list[1]][words_list[2]], list):
                    if words_list[3] == "None":
                        getattr(state, words_list[0])[words_list[1]][words_list[2]] = []
                    else:
                        getattr(state, words_list[0])[words_list[1]][words_list[2]] = [words_list[3]]
                elif isinstance(getattr(state, words_list[0])[words_list[1]][words_list[2]], str):
                    getattr(state, words_list[0])[words_list[1]][words_list[2]] = words_list[3]
                elif isinstance(getattr(state, words_list[0])[words_list[1]][words_list[2]], bool):
                    getattr(state, words_list[0])[words_list[1]][words_list[2]] = custom_bool(words_list[3])
            elif size==1:
                if isinstance(getattr(state, words_list[0])[words_list[1]], list):
                    if words_list[2] == "None":
                        getattr(state, words_list[0])[words_list[1]] = []
                    else:
                        getattr(state, words_list[0])[words_list[1]] = [words_list[2]]
                elif isinstance(getattr(state, words_list[0])[words_list[1]], str):
                    getattr(state, words_list[0])[words_list[1]] = words_list[2]
                elif isinstance(getattr(state, words_list[0])[words_list[1]], bool):
                    getattr(state, words_list[0])[words_list[1]] = custom_bool(words_list[2])
            # elif size==0:
            #     getattr(state, words_list[0])[0] = words_list[1]
            #     if isinstance(getattr(state, words_list[0]), list):
            #         getattr(state, words_list[0]) = [words_list[1]]
            #     elif isinstance(getattr(state, words_list[0])[words_list[1]], str):
            #         getattr(state, words_list[0]) = words_list[2]
            #     elif isinstance(getattr(state, words_list[0])[words_list[1]], bool):
            #         getattr(state, words_list[0])[words_list[1]] = custom_bool(words_list[2])
    return state

def split_line_and_filter(line):
    # Split the line based on delimiters and filter out empty strings
    words = [word.strip() for word in re.split(r'[(),]', line) if word.strip()]
    return words

def find_extra_facts_added(list1, list2):
    # Find lines in list2 that are not in list1
    extra_lines = [line for line in list2 if line not in list1]
    return extra_lines

def extract_lines_between_markers(output, start_marker, end_marker):
    # Split the output into lines
    lines = output.split('\n')

    # Find the indices of the start and end markers
    start_index = next((i for i, line in enumerate(lines) if start_marker in line), None)
    end_index = next((i for i, line in enumerate(lines) if end_marker in line), None)

    # Check if both markers were found
    if start_index is not None and end_index is not None:
        # Extract lines between the start and end markers
        extracted_lines = lines[start_index + 1:end_index]

        return extracted_lines
    else:
        return []
    
def bringAppropriateChangesInTheWorldGRAAL(state, file_path):
    file_path = "/home/sshekhar/Desktop/HATPEHDA-concurrent/dlgp/example.dlgp"
    update_dlgp_fact_list_GRAAL(file_path, "@facts", "@rules", state)
    path_graal_jar = "/home/sshekhar/ssjavaws/"

    import time
    start_time = time.time()

    # bring all the changes here:
    std_output = call_GRAAL_subprocess(path_graal_jar, file_path) 
    end_time = time.time()

    # Calculate the elapsed time
    elapsed_time = end_time - start_time

    # Print the elapsed time
    print(f"Time taken: {elapsed_time*1000} milliseconds")

    return std_output


def call_GRAAL_subprocess(graal_path, file_path):
    import subprocess
    # /home/sshekhar/ssjavaws/graal.jar
    jar_file_path = graal_path + "graal.jar"

    try:
        # Run the Java process and capture the output
        result = subprocess.run(
            ['/usr/lib/jvm/jdk-17/bin/java', '-jar', jar_file_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Store the output in a variable for post-processing
        output = result.stdout

        # Optionally, you can also capture any errors from stderr
        errors = result.stderr

        # Do something with the output and errors
        # print("Output:")
        # print(output)

        # print("\nErrors:")
        # print(errors)

        # Further post-processing can be done here...
        return output
    except subprocess.CalledProcessError as e:
        print(f"Error running the Java process: {e}")


# To do more advanced reasoning based on the knowledge of the agents
# rules: {antecedent_i} => consequent
# consequent can appear only in preconditions and cannot be provided in the initial state or in action effects
# Agents can infer new facts based on what they already know
# provided such rules, robot can manage human's evolution of mental model more effectively
# By taking human's perspective, robot may not communicate this fact to the human knowing that they know the cube is inspected   
def applyRulesToInferNewFactsFromKnownOnes(selected_pair_sa):
    # selected_pair_sa = deepcopy(selected_pair_sa)
    agents = selected_pair_sa.end_agents
    bringAppropriateChangesInTheWorld(agents.state) 
    for ag_state in selected_pair_sa.possible_worlds_for_h: 
        bringAppropriateChangesInTheWorld(ag_state.state) 
    return selected_pair_sa

def bringAppropriateChangesInTheWorld(state):
    # if (state.agent_in_context["R"]["table_context"] == state.agent_in_context["H"]["table_context"] 
    #     and state.agent_at["R"]["agent_at_table"] == state.agent_at["H"]["agent_at_table"]):
    for cube in state.color_cubes:
        if state.inspected_cube_to_place[cube]["inspected"]:
            state.prepare_cleaned_base[cube]["cleaned"] = True   


## pass the designated state, assess what human can observe in their current context in this case
## return "w_the_possible_state_to_keep" as "to keep" state if values of the variables that are 
## observed by human in state and w_the_possible_state_to_keep are the same  
## The idea is to remove all possible states from human mental model of which human is uncertain about 
## such that human discards them by visualizing the current environment  
def utilizeContextForAppropriateSituAssessment_wrt_designated_state_old(state, w_the_possible_state_to_keep):
    
    # state_post_sa = None #appropriate ds?
    
    # In the paper, formally they will be provided as rules that will have below interpretation  
    # FORMAT === {antecedent_i} => consequent

    # E.g., if human is in the context of table and present at the table at the same time
    # then they will assess all cubes orientation on the table or whether the robot holds a cube etc.
    # Note that we will specify only a single consequent that is OBSERVABLE w.r.t. an antecedent (i.e. a formula)
    # (these rules will be "stratified" -- divided into multiple strata -- could be interesting while writing)
    
    # return False

    if (state.agent_in_context["R"]["table_context"] == state.agent_in_context["H"]["table_context"] 
        and state.agent_at["R"]["agent_at_table"] == state.agent_at["H"]["agent_at_table"]):
        # state.agent_in_context["R"]["table_context"] == "table" and state.agent_at["H"]["agent_at_table"] == "table":
        """
        for cube_name in state.color_cubes:
            if (state.holding["R"] == cube_name):
                if (w_the_possible_state_to_keep.holding["R"] != cube_name):
                    return None
                # w_the_possible_state_to_keep.color_cubes[cube_name]["on"] = []
                # w_the_possible_state_to_keep.cube_at_table[cube_name]["at_table"] = None
        """

        # focus: on at_table(cube) fact only:
        for cube in state.color_cubes:
            if (state.cube_at_table[cube]["at_table"] != w_the_possible_state_to_keep.cube_at_table[cube]["at_table"]):
                return None
        
        # focus: on box_at_table if it is empty or it contains cubes
        # the bottom two checks are valid only if the boxes are transparent 
        for box in state.box_at_table:     
            if not state.box_transparent_type[box]["type"] == "transparent":
                continue       
            if (state.box_at_table[box]["empty"] != w_the_possible_state_to_keep.box_at_table[box]["empty"]):
                return None
        for box in state.box_containing:
            if not state.box_transparent_type[box]["type"] == "transparent":
                continue
            for cube in state.box_containing[box]["contains"]:
                if not (cube in w_the_possible_state_to_keep.box_containing[box]["contains"]):
                    return None           
            
        # focus: on "cube on something" fact only:
        for cube in state.color_cubes:
            if (state.color_cubes[cube]["on"] != w_the_possible_state_to_keep.color_cubes[cube]["on"]):
                return None

        # focus: on "cubes held by the robot" fact only:
        for cube in state.color_cubes:
            if (state.holding["R"] != w_the_possible_state_to_keep.holding["R"]):
                return None         
                
        """
        # focus: on inspected cube fact only:
        for cube in state.inspected_cube_to_place:
            if (state.inspected_cube_to_place[cube]["inspected"] != 
                w_the_possible_state_to_keep.inspected_cube_to_place[cube]["inspected"]):
                return None            
        """

        # focus: what's there at different locations
        for loc in state.locations:
            if (state.locations[loc] != 
                w_the_possible_state_to_keep.locations[loc]):
                return None

        """
        # what we want in reality is to fix these states with right variable's values
        for loc in state.solution:
            if state.locations[loc] != None:
                w_the_possible_state_to_keep.color_cubes[state.locations[loc]]["on"] = []
                w_the_possible_state_to_keep.cube_at_table[state.locations[loc]]["at_table"] = None
                w_the_possible_state_to_keep.locations[loc] = state.locations[loc]
        ######
        """       
        if (state.agent_in_context["R"]["table_context"] == state.agent_in_context["H"]["table_context"] 
        and state.agent_at["R"]["agent_at_table"] == state.agent_at["H"]["agent_at_table"]):
            print()
    return "keep"   


# all important comments appear where the original function is written  
def utilizeContextForAppropriateSituAssessment_wrt_designated_state(state, w_the_possible_state_to_keep):
    ######
    # state_post_sa = None #appropriate ds?        
    if (state.agent_in_context["R"] == state.agent_in_context["H"] and state.agent_at["R"] == state.agent_at["H"]):
        
        # focus: food_ready is originally inferable
        if (state.cooking_done["food_ready"] != w_the_possible_state_to_keep.cooking_done["food_ready"]):
            return None
                
        ## we need to play with these properties 
        # if (state.washed["vegetable"] != w_the_possible_state_to_keep.washed["vegetable"]):
        #     return None
        if (state.cut["vegetable"] != w_the_possible_state_to_keep.cut["vegetable"]):
            return None
        # if (state.seasoned["vegetable"] != w_the_possible_state_to_keep.seasoned["vegetable"]):
        #     return None
        if (state.boiling["vegetable"] != w_the_possible_state_to_keep.boiling["vegetable"]):
            return None
        if (state.cooking_done["food_ready"] != w_the_possible_state_to_keep.cooking_done["food_ready"]):
            return None

        if state.observability_washed_vegetable["washed"]:
            if (state.washed["vegetable"] != w_the_possible_state_to_keep.washed["vegetable"]):
                return None

        if state.observability_seasoned_vegetable["seasoned"]:
            if (state.seasoned["vegetable"] != w_the_possible_state_to_keep.seasoned["vegetable"]):
                return None
            
    return "keep"

# we can be lazy on the evaluation of situation assessment 
# to update truth values w.r.t. visible from the environment (in the current state), 
# under the right context and/or learned new facts based on knowns
def situationAssessmentPostActionExecution(processed_pairs_to_explore):
    # processed_pairs_to_explore = deepcopy(pairs_to_explore)
    designated_state = processed_pairs_to_explore.end_agents.state

    possible_world_state_to_keep = []
    for world in processed_pairs_to_explore.possible_worlds_for_h:
        res = utilizeContextForAppropriateSituAssessment_wrt_designated_state(designated_state, world.state)        
        if(res != None):
            possible_world_state_to_keep.append(world)
    processed_pairs_to_explore.possible_worlds_for_h = possible_world_state_to_keep
    return processed_pairs_to_explore

# in future: have this comparison appropriately
def are_worlds_logically_different(are_HR_in_the_same_context, x, obj):
    # return True
    res = CM.compare_states(x.state, obj.state)

    # compare their agendas
    new_agenda_r_x = x["R"].agenda
    new_agenda_r_obj = obj["R"].agenda

    # if are_HR_in_the_same_context != True:
    #     print ("")

    if(len(new_agenda_r_x) != len(new_agenda_r_obj)):
        return True
    else:
        for i in range(len(new_agenda_r_x)):
            if new_agenda_r_x[i].is_abstract != new_agenda_r_obj[i].is_abstract:
                return True
            elif new_agenda_r_x[i].name != new_agenda_r_obj[i].name:
                return True
            elif len(new_agenda_r_x[i].parameters) != len(new_agenda_r_obj[i].parameters):
                return True
            else:
                for j in range(len(new_agenda_r_x[i].parameters)):
                    if new_agenda_r_x[i].parameters[j] != new_agenda_r_obj[i].parameters[j]:
                        return True

    # are_HR_in_the_same_context = False                        
    # compare their agendas    
    if are_HR_in_the_same_context:    
        new_agenda_r_x = x["H"].agenda
        new_agenda_r_obj = obj["H"].agenda
        if(len(new_agenda_r_x) != len(new_agenda_r_obj)):
            return True
        else:
            for i in range(len(new_agenda_r_x)):
                if new_agenda_r_x[i].is_abstract != new_agenda_r_obj[i].is_abstract:
                    return True
                elif new_agenda_r_x[i].name != new_agenda_r_obj[i].name:
                    return True
                elif len(new_agenda_r_x[i].parameters) != len(new_agenda_r_obj[i].parameters):
                    return True
                else:
                    for j in range(len(new_agenda_r_x[i].parameters)):
                        if new_agenda_r_x[i].parameters[j] != new_agenda_r_obj[i].parameters[j]:
                            return True
    
    return not res
 
def exploration_step_tt(pairs_to_explore, allowed_to_signal, goal_test):
    global g_current_agent

    selected_pair_before_sa = select_pair_to_explore(pairs_to_explore)

    # if selected_pair_before_sa.previous != None and selected_pair_before_sa.previous.node_done == "DONE":
    #     return pairs_to_explore

    # it removes all the possible worlds for which human can differentiate them from the 
    # designated world clearly
    selected_pair_sa = situationAssessmentPostActionExecution(selected_pair_before_sa)
    # selected_pair_sa = selected_pair_before_sa

    # 1. python based calls to external functions (like many state of the art work)
    # selected_pair = applyRulesToInferNewFactsFromKnownOnes(selected_pair_sa)
    selected_pair = selected_pair_sa
    
    # selected_pair = selected_pair_sa

    # 2. Below we use a subroutine that calls an external KB e.g., GRAAL. (Expected to be very slow.)
    # selected_pair = applyRulesToInferNewFactsFromKnownOnesGRAAL(selected_pair_sa)

    # test - print state
    # CM.print_state(selected_pair_before_sa.end_agents.state)

    # for world in selected_pair_before_sa.possible_worlds_for_h:
    #     for world1 in selected_pair_before_sa.possible_worlds_for_h:
    #         print(world == world1)
    

    # identify last active agent, determine the current acting agent
    if selected_pair.is_begin():
        acting_agent = CM.g_starting_agent
    elif selected_pair.human_action.is_wait_turn():
        acting_agent = "H"
    elif selected_pair.robot_action.is_wait_turn():
        acting_agent = "R"
    else:
        raise Exception("Problem")    

    # '''
    dup_world_list = deepcopy(selected_pair.possible_worlds_for_h)
    
    # are_HR_in_the_same_context = True

    # checking the H-R context - copy        
    are_HR_in_the_same_context = ((selected_pair.end_agents.state.agent_in_context["R"] == selected_pair.end_agents.state.agent_in_context["H"]) 
            and (selected_pair.end_agents.state.agent_at["R"] == selected_pair.end_agents.state.agent_at["H"]))
        
    # this feature is added to decompose the tree in the post processing
    if are_HR_in_the_same_context:
        selected_pair.copresence = True
    else:
        selected_pair.copresence = False

    # for debugging 
    if(len(dup_world_list) >= 14):
        print()

    print("\nsize before: ", len(dup_world_list))
    # filtered_world_list = list(filter(lambda x: any(are_objects_technically_different(x, obj) for obj in dup_world_list), dup_world_list))
    unique_worlds_state_agenda = set()

    # CM.print_state(selected_pair.end_agents.state)

    for virtual_world in dup_world_list:
        if not are_worlds_logically_different(are_HR_in_the_same_context, virtual_world, selected_pair.end_agents):
            continue
        is_unique = True
        for unique_obj in unique_worlds_state_agenda:
            if not are_worlds_logically_different(are_HR_in_the_same_context, virtual_world, unique_obj):
                is_unique = False
                break
        if is_unique:
            unique_worlds_state_agenda.add(virtual_world)

    print("size after: ", len(unique_worlds_state_agenda))

    if(len(unique_worlds_state_agenda) > 14):
        print()
    
    # set the global variable
    global max_number_of_worlds_evaluated
    if len(unique_worlds_state_agenda) > max_number_of_worlds_evaluated:
        max_number_of_worlds_evaluated = len(unique_worlds_state_agenda)

    selected_pair.possible_worlds_for_h = unique_worlds_state_agenda    
    # '''
    
    # selected_pair = selected_pair_sa    
       
    if acting_agent == "H":        
        # this should not only change the end_states but also relevant propositions of all possible states
        selected_pair_loc = deepcopy(selected_pair)
        ref = get_applied_refinement("H", selected_pair_loc, selected_pair_loc.end_agents)
        pairs = []
        r_pass = CM.Action.create_passive("R", "WAIT_TURN")
        
        ### This blockcode is specifically for appending the signaling macro in the policy
        ### I have tried to keep this part clean and seperate from the main code 
        ### To not allow robot to signal, disable allowed_to_signal in the main() 
        if allowed_to_signal:
            for dec in ref.applied_decomps:
                if dec.PT != None and dec.PT.name == "passive_wait_for_signal":                
                    if "box_1" in dec.PT.parameters: 
                        # manual - which box contain cube(s) from the main table
                        which_cube = None
                        state = selected_pair.end_agents.state
                        for c in state.cube_belongs_table:
                            if (c in state.box_containing["box_2"]["contains"]):
                                which_cube = c
                        pt = CM.PrimitiveTask("take_out", [which_cube, "box_2"], None, 0, "R")
                        at = CM.AbstractTask("Place_1_primitive", [which_cube, "box_2"], None, 0, "R")
                        # at = CM.AbstractTask("Pick_n_place", [], None, 0, "R")
                    else:
                        # manual - which box contain cube(s) from the main table
                        which_cube = None
                        state = selected_pair.end_agents.state
                        for c in state.cube_belongs_table:
                            if (c in state.box_containing["box_1"]["contains"]):
                                which_cube = c
                        pt = CM.PrimitiveTask("take_out", [which_cube, "box_1"], None, 0, "R")
                        at = CM.AbstractTask("Place_1_primitive", [which_cube, "box_1"], None, 0, "R")
                        # at = CM.AbstractTask("Pick_n_place", [], None, 0, "R")

                    dec.end_agents["R"].agenda[:0] = [pt, at]
                    for possible_world in selected_pair.possible_worlds_for_h:
                        possible_world.agents["R"].agenda[:0] = [pt, at]
                        possible_world.agents["H"].agenda = dec.end_agents["H"].agenda
                    pairs.append(ActionPair(dec.next_action, r_pass, dec.end_agents, selected_pair.possible_worlds_for_h))
        ######       
        #############                  
        
        for dec in ref.applied_decomps:     
            if dec.PT != None and dec.PT.name == "passive_wait_for_signal": 
                continue    ######## we do not allow PASS in this case ########
            pairs.append(ActionPair(dec.next_action, r_pass, dec.end_agents, selected_pair_loc.possible_worlds_for_h))

        selected_pair_loc = deepcopy(selected_pair)
        pass_added = False # to manage pair of actions (H:PASS, R:PASS)
        for p in pairs:
            if p.human_action.is_passive():
                p.human_action.parameters.append("PASS")
                pass_added = True
                break
        if not pass_added and are_HR_in_the_same_context:
            # print()
            pairs.append(ActionPair(CM.Action.create_passive("H", "PASS"), r_pass, selected_pair_loc.end_agents, selected_pair_loc.possible_worlds_for_h))
            # pairs.insert(0, ActionPair(CM.Action.create_passive("H", "PASS"), r_pass, selected_pair_loc.end_agents, selected_pair_loc.possible_worlds_for_h))

        # stop at this point
        flag = False
        for p in pairs:
            if("communicate" in p.human_action.name):
                flag = True
        if flag:
            print()

    else:
        # Now it is the robot's turn        
        # I bring the high-level concept for situation_assessment(agents) from the PlanRob version
        # yes/no -- agents.copresent()
        # I make it more general and introduce context (antecedent --> consequent)

        # We build the possible worlds based on current possible worlds (non-designated ds "end_agent" -- which human considers it possible) 
        # in "selected_pair.possible_worlds_for_h" --- go over all possible worlds
        # Note that the pair below for the robot is what actually robot performed in reality with H being passive when the robot acts 

        # for each selected pair: there could be many "agents" ds --- out of which there will be only one real "agents" ds
        # we segregate it by selected_pair.possible_worlds_for_h and selected_pair.end_agents            

        # checking the H-R context        
        are_HR_in_the_same_context = ((selected_pair.end_agents.state.agent_in_context["R"] == selected_pair.end_agents.state.agent_in_context["H"]) 
            and (selected_pair.end_agents.state.agent_at["R"] == selected_pair.end_agents.state.agent_at["H"]))
        
        # are_HR_in_the_same_context = ((selected_pair.end_agents.state.agent_in_context[acting_agent]["table_context"] == 
        #         selected_pair.end_agents.state.agent_in_context["H"]["table_context"]) 
        #      and (selected_pair.end_agents.state.agent_at[acting_agent]["agent_at_table"] == 
        #         selected_pair.end_agents.state.agent_at["H"]["agent_at_table"]))        

        """
        Things would be a bit more complex when agents are co-present
        this is due to the fact that, human might have a list of possible worlds, from the past execution
        as we know, robot knows the ground truth -- it can apply an action (decomposition) that is allowed in real designated world "end_agent" ds
        however if that robot action can be observed by the human in the environment, the execution may reduce the world uncertainity w.r.t. H
        """      

        # If they are in or same/different context -- the main exploration mechanism would change
        # are_HR_in_the_same_context = True

        if not are_HR_in_the_same_context:
            pairs = exploration_when_HR_not_insame_context(selected_pair)          
        else:
            pairs = exploration_when_HR_insame_context(selected_pair)   

    human_options = arrange_pairs_in_HumanOption(pairs)
    new_step = Step(parent=selected_pair.get_in_step())
    new_step.init(human_options, selected_pair)

    lg.debug(f"{new_step.str()}")

    new_explo_pairs = []

    # new pairs of actions are formed at this stage 
    for p in new_step.get_pairs():
        # if over, continue
        # if two consecutive passive pairs, continue
        if p.is_final():            
            if goal_test[0]:
                goal_test[1] = "goal"
            continue
        if p.is_passive():
            if p.previous!=None and p.previous.is_passive() and not p.previous.is_begin():                
                p.node_pass = "pass"
                if goal_test[0]:
                    goal_test[1] = "pass"
                continue            
        new_explo_pairs.append(p)
    
    # flag = False
    # if(pairs[0].human_action.parameters[0] == "WAIT_TURN" and pairs[0].robot_action.parameters[0] == "IDLE" and pairs[0].robot_action.parameters[1] == "PASS"):
    #     pairs_parent = pairs[0].previous    
    #     if(pairs_parent.robot_action.parameters[0] == "WAIT_TURN" and pairs_parent.human_action.parameters[0] == "IDLE" and pairs_parent[1].human_action.parameters[1] == "PASS"):
    #         print("")
    #         flag = True

    # if(pairs[0].robot_action.parameters[0] == "WAIT_TURN" and pairs[0].human_action.parameters[0] == "IDLE" and pairs[0].human_action.parameters[1] == "PASS"):
    #     pairs_parent = pairs[0].previous    
    #     if(pairs_parent.human_action.parameters[0] == "WAIT_TURN" and pairs_parent.robot_action.parameters[0] == "IDLE" and pairs_parent.robot_action.parameters[1] == "PASS"):
    #         print("")
    #         flag = True
    

    if(len(new_explo_pairs)==0):
        print("")
    print("Current agent ", acting_agent)    

    # if flag:
    #     return []    
    
    return new_explo_pairs + pairs_to_explore       ## DFS - old
    # return pairs_to_explore + new_explo_pairs       ## BFS - old

### 1 ###
def select_pair_to_explore(pairs_to_explore) -> ActionPair:
    selected_pair = pairs_to_explore.pop(0)
    # selected_pair = pairs_to_explore[0]
    # already_explored.append(selected_pair)
    # selected_pair = deepcopy(selected_pair_loc)
    # i tried deepcopy it did not work

    lg.debug(f"Selected pair: {selected_pair} (from step {selected_pair.get_in_step()})")
    lg.debug(CM.str_agents(selected_pair.end_agents))
    return selected_pair

### 2 ###
def compute_parallel_pairs(selected_pair: ActionPair) -> List[ActionPair]:
    #2# Compute parallel pairs (and L.R.D. pairs)
    
    # Compute H starting pairs
    HS_pairs = []
    HS_applied_ref_h = get_applied_refinement("H", selected_pair.end_agents)
    for h_ap_dec in HS_applied_ref_h.applied_decomps:
        HS_applied_ref_r = get_applied_refinement("R", h_ap_dec.end_agents)
        for r_ap_dec in HS_applied_ref_r.applied_decomps:
            pair = ActionPair(h_ap_dec.next_action, r_ap_dec.next_action, r_ap_dec.end_agents)
            HS_pairs.append(pair)
    
    # Compute R starting pairs
    RS_pairs = []
    RS_applied_ref_r = get_applied_refinement("R", selected_pair.end_agents)
    for r_ap_dec in RS_applied_ref_r.applied_decomps:
        RS_applied_ref_h = get_applied_refinement("H", r_ap_dec.end_agents)
        for h_ap_dec in RS_applied_ref_h.applied_decomps:
            pair = ActionPair(h_ap_dec.next_action, r_ap_dec.next_action, h_ap_dec.end_agents)
            RS_pairs.append(pair)
    
    # Check if both agents are active
    h_active = check_list(HS_pairs, lambda x: not x.human_action.is_passive())!=None
    r_active = check_list(RS_pairs, lambda x: not x.robot_action.is_passive())!=None
    agents_active = h_active and r_active

    # Create LRD pairs
    lrd_pairs = []
    if agents_active:
        lrd_action = CM.Action.create_passive("H", "PASS")
        for RS_pair in RS_pairs:
            already_exist = check_list(lrd_pairs, lambda x: CM.Action.are_similar(x.robot_action, RS_pair.robot_action))!=None
            if not already_exist:
                new_agents = get_agents_after_action(deepcopy(selected_pair.end_agents), RS_pair.robot_action) 
                new_agents["H"].planned_actions.append( lrd_action )
                new_lrd_pair = ActionPair(lrd_action, RS_pair.robot_action, new_agents)
                lrd_pairs.append(new_lrd_pair)

    # Parallel pairs
    parallel_pairs = []
    for HS_pair in HS_pairs:
        if not h_active:
            parallel_pairs.append(HS_pair)
        elif check_list(RS_pairs, lambda x: CM.Action.are_similar(HS_pair.robot_action, x.robot_action)\
                and CM.Action.are_similar(HS_pair.human_action, x.human_action))!=None:
            # check shared resource
            if (HS_pair.human_action.shared_resource==None or HS_pair.robot_action.shared_resource==None)\
                or (HS_pair.human_action.shared_resource != HS_pair.robot_action.shared_resource):
                parallel_pairs.append(HS_pair)

    # check if one human action is missing, added with WAIT pair
    for HS_pair in HS_pairs:
        if check_list(parallel_pairs, lambda ppair: CM.Action.are_similar(ppair.human_action, HS_pair.human_action))==None:
            r_wait_action = CM.Action.create_passive("R", "WAIT")
            new_agents = get_agents_after_action(deepcopy(selected_pair.end_agents), HS_pair.human_action)
            new_wait_pair = ActionPair(HS_pair.human_action, r_wait_action, new_agents)
            parallel_pairs.append(new_wait_pair)

    return parallel_pairs + lrd_pairs

### 3 ###
def arrange_pairs_in_HumanOption(parallel_pairs: List[ActionPair]) -> List[HumanOption]:
    #3# Arrange all pairs into HumanOptions
    raw_options = {}
    for p in parallel_pairs:
        if not p.human_action in raw_options:
            raw_options[p.human_action] = [p]
        else:
            raw_options[p.human_action].append(p)
    
    human_options = []
    for raw_o in raw_options:
        ha = HumanOption(raw_options[raw_o])
        human_options.append(ha)

    return human_options

### 4 ###
def identify_CRA(new_step: Step):
    # Identify C.R.A. (Common Robot Actions)
    cra_candidates = new_step.human_options[0].robot_actions[:]
    for ho in new_step.human_options[1:]:
        j = 0
        while j<len(cra_candidates):
            candidate = cra_candidates[j]

            found = check_list(ho.robot_actions, lambda x: CM.Action.are_similar(candidate, x))!=None
            if not found:
                cra_candidates.pop(j)
            else:
                j+=1
    return cra_candidates

### 4 bis ###
def add_systematic_r_skip(new_step: Step, selected_pair):
    for ho in new_step.human_options:
        ho.add_robot_passive("SKIP")

### 5 ###
def add_robot_skips(new_step: Step, selected_pair):
    # if the robot has actions requiring a successful ID
    # i.e., action that are not Common Robot Action
    for ho in new_step.human_options:
        found = False
        for p in ho.action_pairs:
            if check_list(new_step.CRA, lambda car: CM.Action.are_similar(car, p.robot_action))!=None:
                found = True
                break
        if found:
            continue
        else:
            ho.add_robot_passive("SKIP")

### 6 ###
def add_robot_leaves(new_step: Step, selected_pair):
    pass

### 7 ###
def get_pairs_to_explore(new_step: Step, previous_pairs_to_explore: List[ActionPair]):
    new_explo_pairs = []
    
    # add all pairs except double passive
    for pair in new_step.get_pairs():
        if not pair.is_passive():
            new_explo_pairs.append(pair)

    return new_explo_pairs + previous_pairs_to_explore


#####################################################
## REFINEMENT (w.r.t. a world of an episemic state)##
#####################################################
def get_applied_refinement_wrt_a_possible_world(agent_name, agents):
    """
    Refines agent's agenda and applies it.
    I.e. the PT of each decomp is applied and inactivity actions may be inserted.
    Triggers are checked here.
    """

    # Shashank: choose one epistemic state 
    # For each world (e.g., w0) within it, compute all possible events/actions that can be applied
    # For human: for each pair (wi, wj) -- if there exists (ai, aj) -- they will ofcourse be indistinguishable 
    # the resulting new worlds will be indistinguishable as well

    # for the robot, we know the real world in the epistemic state
    # see which all are applicable actions in this world
    
    # print("{}- Refine agenda".format(agent_name))
    # shashank: considers one full state (e.g., w0 of an epistemic state) at a time
    # can serve as a basic building block -- it brings all possible ways of decomposing the (shared) task
    # assuming this world (w0) is the real world 
    refinement = refine_agenda(agent_name, agents)
    # print("refinement = ")
    # refinement.show()

    # What this step does is, it takes the refinement and update it with agent datastructure
    # end_agents -- it has the current state (HnR), without the effects of the primitive actions being applied
    applied_ref = CM.AppliedRefinement(refinement, agents)

    # Within this for loop: for each decomposition, it takes the first action in the priority list,
    # applies it to the (single) state (such that it updates the beliefs for both the agents), then updates the 
    # remaining subtasks as the updated agenda w.r.t. the next state generated.
    # 
    for ap_dec in applied_ref.applied_decomps:
        if not CM.DecompType.OK == ap_dec.type:
            # TODO check if no triggers are forgotten when creating inactivity actions
            if CM.DecompType.NO_APPLICABLE_METHOD == ap_dec.type:
                lg.debug("NO_APPLICABLE_METHOD => WAIT added")
                action = CM.Action.create_passive(agent_name, "WAIT")
                ap_dec.type = CM.DecompType.OK
            elif CM.DecompType.AGENDA_EMPTY == ap_dec.type:
                # print("AGENDA_EMPTY => IDLE added")
                action = CM.Action.create_passive(agent_name, "IDLE")
                ap_dec.type = CM.DecompType.OK
        elif CM.DecompType.OK == ap_dec.type:
            # Apply the PT operator's effects to both beliefs
            # Get the PT operator
            if not CM.g_static_agents[agent_name].has_operator_for(ap_dec.PT):
                raise Exception("Agent {} doesn't have an operator for {}".format(agent_name, ap_dec.PT))
            op = CM.g_static_agents[agent_name].operators[ap_dec.PT.name]

            # Shashank: apply operator to both beliefs
            result = op.apply(ap_dec.end_agents, ap_dec.PT)

            if CM.OpType.NOT_APPLICABLE == result:
                lg.debug(str(ap_dec.PT) + " not applicable... WAIT inserted")
                ap_dec.new_agenda = [ap_dec.PT] + ap_dec.new_agenda
                action = CM.Action.create_passive(agent_name, "WAIT")
            else:
                action = CM.Action.cast_PT2A(ap_dec.PT, result[0], result[1])

            check_triggers(ap_dec.end_agents)

        ap_dec.next_action = action
        ap_dec.end_agents[agent_name].agenda = ap_dec.subtasks[1:] + ap_dec.new_agenda
        ap_dec.end_agents[agent_name].planned_actions.append( action )

    return applied_ref



################
## REFINEMENT ##
################
def get_applied_refinement(agent_name, selected_pair, agents):
    """
    Refines agent's agenda and applies the refinements.
    I.e. the PT of each decomp is applied and inactivity actions may be inserted.
    Triggers are checked here.
    """

    # In principle: we chose an epistemic state -- an currently focusing on a possible world i.e., I/P:agents 
    # For that world, compute all possible refinements that can be applied
    # Since we are interested in capturing the "human confusion" when H and R are not co-present...
    # We must consider each such world and if that is the world in reality how the robot would have progressed, given that it is R's turn 
    # For the robot, we know the real world in all epistemic states -- our simplifying assumption
    
    # print("{}- Refine agenda".format(agent_name))
    refinement = refine_agenda(agent_name, selected_pair, agents)
    # print("refinement = ")
    # refinement.show()

    # What this step does is, it takes the refinement and updates it with agent data structure 
    # end_agents -- it has the current state (HnR), without the effects of the primitive actions being applied
    applied_ref = CM.AppliedRefinement(refinement, agents)

    # (within this for loop) For each possible decomposition, it takes the first action in the priority list,
    # applies it to the (single) state (such that it updates the beliefs for both agents), then updates the 
    # remaining subtasks as the updated agenda w.r.t. the next state generated. 
    does_this_list_have_comm = False    
    for ap_dec in applied_ref.applied_decomps:
        if ap_dec.PT != None and "communicate" in ap_dec.PT.name:
            does_this_list_have_comm = True
            save_decomp = deepcopy(ap_dec)

    for ap_dec in applied_ref.applied_decomps:
        if not CM.DecompType.OK == ap_dec.type:
            # TODO check if no triggers are forgotten when creating inactivity actions
            if CM.DecompType.NO_APPLICABLE_METHOD == ap_dec.type:
                lg.debug("NO_APPLICABLE_METHOD => WAIT added")
                action = CM.Action.create_passive(agent_name, "WAIT")
                ap_dec.type = CM.DecompType.OK
            elif CM.DecompType.AGENDA_EMPTY == ap_dec.type:
                # print("AGENDA_EMPTY => IDLE added")
                action = CM.Action.create_passive(agent_name, "IDLE")
                ap_dec.type = CM.DecompType.OK
        elif CM.DecompType.OK == ap_dec.type:
            # Apply the PT operator's effects to both beliefs
            # Get the PT operator
            if not CM.g_static_agents[agent_name].has_operator_for(ap_dec.PT):
                raise Exception("Agent {} doesn't have an operator for {}".format(agent_name, ap_dec.PT))
            op = CM.g_static_agents[agent_name].operators[ap_dec.PT.name]

            # Shashank: apply operator to both beliefs
            # verify this selected_pair.possible_worlds_for_h
            if (ap_dec.PT.agent == "H" and ap_dec.PT.name == "pick" and "y2" in ap_dec.PT.parameters):
                print(" ")
            result = op.apply(selected_pair, ap_dec.end_agents, ap_dec.PT)

            # Note: it can be applied in the real world but not in another possible world
            # We can always add this action's preconditions as new communication actions
            # in the new agenda -- similar to the way it is added during method applicability 
            if CM.OpType.NOT_APPLICABLE == result:
                lg.debug(str(ap_dec.PT) + " not applicable... WAIT inserted")
                ap_dec.new_agenda = [ap_dec.PT] + ap_dec.new_agenda
                action = CM.Action.create_passive(agent_name, "WAIT")
            else:
                action = CM.Action.cast_PT2A(ap_dec.PT, result[0], result[1])

            check_triggers(ap_dec.end_agents)

        ap_dec.next_action = action
        ap_dec.end_agents[agent_name].agenda = ap_dec.subtasks[1:] + ap_dec.new_agenda
        ap_dec.end_agents[agent_name].planned_actions.append( action )

        # shashank -- update the agendas in the possible worlds as well
        if agent_name == "H":
            for possible_world in selected_pair.possible_worlds_for_h:
                possible_world.agents["H"].agenda = ap_dec.end_agents[agent_name].agenda

    # In this refinement list, if for a decomposition there is a way a human is communicating
    # add a fresh decomposition w.r.t. the robot to signal the human about a fact (by acting in the real world) 
    # Refer to the original world, see which cube can be taken out that will work as a signal
    # human will continue with a usual task list  
    # step 1: go over all the refinements decomposition
    # step 2: if there is a communication
    # step 3: in a fresh decomposition add take-out and Place subtask for the robot to signal
    # step 4: test it properly    
    if(does_this_list_have_comm):        
        action = CM.Action.create_passive_signal("H", "WAIT-FOR-SIGNAL")
        save_decomp.PT.name = "passive_wait_for_signal" 
        save_decomp.next_action = action
        save_decomp.end_agents[agent_name].agenda = save_decomp.subtasks[1:] + save_decomp.new_agenda
        save_decomp.end_agents[agent_name].planned_actions.append( action )

        # subtasks = []
        # subtasks.append(CM.AbstractTask("Place_1", [], task_to_refine, i, agent_name))
        # # param = m.get_m_precond(state, task_to_refine)
        # # subtasks.append(CM.AbstractTask("Communicate", param, task_to_refine, i, agent_name ))
        # # it is not an ideal way to deal with communication though (a more refined way is for future work)
        # new_agenda = [task_to_refine] + new_agenda
        # list_decomps.append(CM.Decomposition(subtasks, agenda=new_agenda))
        applied_ref.applied_decomps.append(save_decomp)

    return applied_ref

# when it is human, by defaults there should be a common agenda in all possible world stages
# that is same task to execute next as well as the task decomposition is applicable in all possible states
def refine_agenda(agent_name, selected_pair, in_agents):
    """
    Refines the agenda of the given agent until reaching a primitive task.
    Return a refinement, including decompositions for each applied different method.
    """

    static_agent = CM.g_static_agents[agent_name]
    state = deepcopy(in_agents.state)
    new_agenda = in_agents[agent_name].agenda[:]

    refinement = CM.Refinement()
    refinement.add(CM.Decomposition([]))    

    # Check if agenda is empty (no task to refine)
    if new_agenda == []:
        refinement.decompos[0].new_agenda = []
        refinement.decompos[0].type = CM.DecompType.AGENDA_EMPTY
    else:
        next_task = new_agenda.pop(0)
        # print("Task to refine: {}".format(next_task))
        
        refinement.decompos[0].subtasks = [next_task]
        refinement.decompos[0].new_agenda = new_agenda

        i=0
        # While we didn't reach the end of each decomposition, we start with one decomposition
        while i < len(refinement.decompos):
            current_decomp = refinement.decompos[i]
            # print("decomp i= {}".format(i))
            # While first subtask of current decomposition isn't a PT and is not done in this state (we keep refining it)
            while not current_decomp.first_task_is_PT_not_done(agent_name, state):
                task = current_decomp.subtasks[0]
                next_subtasks = current_decomp.subtasks[1:]

                # Either already refine the task with methods or 
                if task.is_abstract and static_agent.has_method_for(task):

                    # In the EpiP approach, we test that the method's precondition holds in all possible worlds
                    # I believe this list of decomposition is applicable in all possible (EpiP) states
                    # list_decompo = refine_method(task, selected_pair, state, new_agenda)
                    list_decompo = refine_method(task, selected_pair, state, current_decomp.new_agenda)

                elif not task.is_abstract and static_agent.has_operator_for(task): 
                    list_decompo = [CM.Decomposition([task], agenda=new_agenda)]
                else:
                    raise Exception("task={} can't be handled by agent {}.".format(task, agent_name))

                # END, if no method is applicable
                if list_decompo == []:
                    current_decomp.subtasks = next_subtasks

                    # current_decomp.new_agenda = [task] + new_agenda // old code
                    current_decomp.new_agenda = [task] + current_decomp.new_agenda

                    current_decomp.type = CM.DecompType.NO_APPLICABLE_METHOD
                    lg.debug("no possible decomposition: \t{} => {}".format(task, current_decomp.type))
                    break
                # There are applicable methods
                else:
                    # If we continue to refine with next tasks
                    need_continue = False
                    # If current method refines into nothing
                    if list_decompo[0].subtasks==[]:
                        lg.debug(CM.bcolors.OKGREEN + "\trefines into nothing" + CM.bcolors.ENDC)
                        need_continue = True
                    # If next task is an operator already done
                    elif current_decomp.first_task_is_PT_done(agent_name, state): # CHECK list_decomp ? 
                        lg.debug(CM.bcolors.OKGREEN + "\talready done" + CM.bcolors.ENDC)
                        need_continue = True
                    if need_continue:
                        # print("NEED_CONTINUE")
                        # If there are other subtasks we continue by refining the next one
                        if len(next_subtasks)>0:
                            lg.debug("\tcontinue .. next_subtasks={}".format(next_subtasks))
                            current_decomp.subtasks = next_subtasks
                        # No other subtasks, we have to pop the next task in agenda to continue
                        else:
                            # END, If the agendas are empty
                            if new_agenda==[]:
                                current_decomp.subtasks = next_subtasks
                                current_decomp.type = CM.DecompType.AGENDA_EMPTY
                                lg.debug("\t{} => {}".format(task, current_decomp.type))
                                break
                            # Agenda isn't empty, we can continue with next task in agenda
                            else:
                                next_task = new_agenda.pop(0)
                                lg.debug("\tcontinue with next_task popped from agenda {}".format(next_task))
                                current_decomp.subtasks = [next_task]
                    # Update subtasks list and add new decompositions for each additional applicable methods
                    else:
                        current_decomp.subtasks = list_decompo[0].subtasks + next_subtasks
                        # shahank -- update the agenda when communication was added
                        if list_decompo[0].new_agenda != []:
                            current_decomp.new_agenda = list_decompo[0].new_agenda
                        for j in range(1, len(list_decompo)):
                            j_subtasks = list_decompo[j].subtasks + next_subtasks
                            # print("\t\tdecomposition {} : created : {}".format(j, j_subtasks))
                            refinement.add(CM.Decomposition(j_subtasks, agenda=new_agenda))

            # End of the decomposition reached, we look for the next one
            # print("\tend {}".format(i))

            # shashank - how does it know that current_decomp.subtasks[0] is a primitive task alsways?
            # see break condition when list_decompo is empty! line 969 "**if list_decompo == []:**"
            if len(current_decomp.subtasks)>0:
                current_decomp.PT = current_decomp.subtasks[0]
            i+=1

    return refinement

def get_subtask_list(list_decomps, m, i, task_to_refine, selected_pair, state, new_agenda):
    agent_name = task_to_refine.agent
    static_agent = CM.g_static_agents[agent_name]

    # get methods
    # if not static_agent.has_method_for(task_to_refine):
    #     raise Exception("{} has no methods for {}".format(agent_name, task_to_refine))
    # methods = static_agent.methods[task_to_refine.name]

    multi_dec_tuple = m.get_decomp(state, task_to_refine) # list(list(tuple(task_name: str, *params: Any)))
    for dec_tuple in multi_dec_tuple:
        subtasks = []
        for tuple in dec_tuple:
            task = tuple[0]
            params = tuple[1:]
            if task in static_agent.methods:
                subtasks.append(CM.AbstractTask(task, params, task_to_refine, i, agent_name))
            elif task in static_agent.operators:
                subtasks.append(CM.PrimitiveTask(task, params, task_to_refine, i, agent_name))
            else:
                raise Exception("{} isn't known by agent {}".format(task, agent_name))

        list_decomps.append(CM.Decomposition(subtasks, agenda=new_agenda))

    return list_decomps


def refine_method(task_to_refine, selected_pair, state, new_agenda):
    agent_name = task_to_refine.agent
    static_agent = CM.g_static_agents[agent_name]

    # get methods
    if not static_agent.has_method_for(task_to_refine):
        raise Exception("{} has no methods for {}".format(agent_name, task_to_refine))
    methods = static_agent.methods[task_to_refine.name]

    # apply each method to get decompositions
    list_decomps = []
    for i,m in enumerate(methods):
        if m.is_done(state, task_to_refine):
            list_decomps.append(CM.Decomposition([]))

        # if the human has an applicable method w.r.t. their next task in the designated world
        # but why only designated? shouldn't it be with any other worlds they believe?
        # RIGHT: so, for practical gain and algorithmic simplicity, I keep it like this for now, 
        # there is no harm in creating new communication protocol based on the world that does not exist 
        # in reality -- we can change the code accordingly

        # In theory, communication based on every possible world can be inserted
             
        # (Note that if they are (back) in the right context) and they can be communicated (asked or told)
        # My IDEA: when this same method is not applicable in at least one of the possible worlds which 
        # humans can assume it as possibly be a true world.
        # Human can be informed (human can ask or can be told) about the preconditions of this method  

        # This is an optimistic approach to deploy a communication action -- inspired from epistemic planning
        # fact: at(R) = Room, as a precond e0 -- indistinguishability relation (e0, e0) -- will retain only those
        # states in which at(R) = Room holds 
        # idea is to communicate the status of a variable as per what the designated world says.
        # In theory, it goes over all the possible worlds considering them as a designated world (from the human's perspective)

        # Moreover, note that we are aware of the kind of task we want to solve -- we use that as prior knowledge

        # going over all possible methods -- this way makes the algorithm SOUND and COMPLETE
        elif m.is_applicable(state, task_to_refine): 

            # let's first verify if the human can be communicated something
            flag_cannot_communicate = True            
            
            if agent_name == "H":
                # the method should not be applicable in all possible worlds! What exactly?
                # there should be at least one world in which what is being communicate (which holds in 
                # the real world and) does not hold in that that human cannot distinguish it with the real world
                
                # this might not work if agents start from different contexts!
                for world in selected_pair.possible_worlds_for_h:
                    if not m.is_applicable(world.state, task_to_refine):
                        flag_cannot_communicate = False; 
                        # get all the variables that do not hold in "world" but in "state" -- the designated world 
                        # communicate them all in a certain order 
                        break
                    
                if not flag_cannot_communicate:
                    # list_decomps = get_subtask_list(list_decomps, m, i, task_to_refine, selected_pair, state, new_agenda)
                    # add right communication subtasks, e.g., (Communicate cube)
                    # study the entire belief state -- create a new method/action w.r.t. each fluent

                    # update the agenda with the communication action(s) or abstract task
                    # shashank -- currently manually done to verify POC -- idea is to have 
                    # a communication (AT/PT) action w.r.t. each fact that can be communicated in a state
                    # I.e. each precondition of this method
                    subtasks = []
                    # for lst in m.get_m_precond(world.state, task_to_refine):
                    #     # HUMAN ASKS ROBOT
                    #     subtasks.append(CM.AbstractTask("Communicate", lst, task_to_refine, i, agent_name))

                    subtasks.append(CM.AbstractTask("Communicate", [], task_to_refine, i, agent_name))

                    # param = m.get_m_precond(state, task_to_refine)
                    # subtasks.append(CM.AbstractTask("Communicate", param, task_to_refine, i, agent_name ))
                    # it is not an ideal way to deal with communication though (a more refined way is for future work)
                    new_agenda = [task_to_refine] + new_agenda
                    list_decomps.append(CM.Decomposition(subtasks, agenda=new_agenda))
                    
                    # subtasks = []
                    # for lst in m.get_m_precond(world.state, task_to_refine):
                    #     if ("box_1" in lst):
                    #         subtasks.append(CM.PrimitiveTask("take_out", ["r1", "box_2"], task_to_refine, i, "R"))
                    #     else:
                    #         subtasks.append(CM.PrimitiveTask("take_out", ["r1", "box_1"], task_to_refine, i, "R"))
                    #     subtasks.append(CM.AbstractTask("Place_1", lst, task_to_refine, i, "R"))

                    # # param = m.get_m_precond(state, task_to_refine)
                    # # subtasks.append(CM.AbstractTask("Communicate", param, task_to_refine, i, agent_name ))
                    # # it is not an ideal way to deal with communication though (a more refined way is for future work)
                    # new_agenda = [task_to_refine] + new_agenda
                    # list_decomps.append(CM.Decomposition(subtasks, agenda=new_agenda))

                    continue            
            
            # the following captures those methods that can be applied in the epistemic state: regardless of uncertainty the human carries
            # note that this is common to both human and the robot -- and basically robot knows the true world 
            if flag_cannot_communicate:
                method_also_applicable_in_all_possible_states = True
                for possible_world in selected_pair.possible_worlds_for_h:
                    if not m.is_applicable(possible_world.state, task_to_refine): 
                        method_also_applicable_in_all_possible_states = False 
                        break
                    
                # dec_tuple = m.get_decomp(state, task_to_refine) # list(list(tuple(task_name: str, *params: Any)))
                if not method_also_applicable_in_all_possible_states and agent_name == "H":
                    continue
                """ ~ """
                # if(len(selected_pair.possible_worlds_for_h)>0):
                #     list_decomps = get_subtask_list(list_decomps, m, i, task_to_refine, selected_pair, selected_pair.possible_worlds_for_h[0].state, new_agenda)
                # else:
                list_decomps = get_subtask_list(list_decomps, m, i, task_to_refine, selected_pair, state, new_agenda)
            
            #### old code below: now in get_subtask_list() function above ####
            # multi_dec_tuple = m.get_decomp(state, task_to_refine) # list(list(tuple(task_name: str, *params: Any)))
            # for dec_tuple in multi_dec_tuple:
            #     subtasks = []
            #     for tuple in dec_tuple:
            #         task = tuple[0]
            #         params = tuple[1:]
            #         if task in static_agent.methods:
            #             subtasks.append(CM.AbstractTask(task, params, task_to_refine, i, agent_name))
            #         elif task in static_agent.operators:
            #             subtasks.append(CM.PrimitiveTask(task, params, task_to_refine, i, agent_name))
            #         else:
            #             raise Exception("{} isn't known by agent {}".format(task, agent_name))

            #     list_decomps.append(CM.Decomposition(subtasks, agenda=new_agenda))

        # let's verify if the robot can communicate something to the human
        # if m.can_communicate(task_to_refine, selected_pair, state):

    return list_decomps

def check_triggers(agents):
    #TODO
    pass

def get_agents_after_action(in_agents, action):
    if action.is_passive():
        return in_agents
    ap_ref = get_applied_refinement(action.agent, in_agents)
    dec = check_list(ap_ref.applied_decomps, lambda x: CM.Action.are_similar(x.next_action, action))
    if dec==None:
        raise Exception("Corresponding decomposition not found!")
    return dec.end_agents


#############
## METRICS ##
#############
def compute_metrics(final_leaves: List[Step]):
    for end_step in final_leaves:
    # for leaf_pair in leaf_pairs:
        leaf_pair = end_step.get_pairs()[0]
        current_metrics = {
            "TimeEndHumanDuty" : end_step.depth-1,
            "HumanEffort" : 0.0,
            "TimeTaskCompletion" : end_step.depth-1,
            "GlobalEffort" : 0.0,
            "RiskConflict" : 0.0,
        }
        human_acted = False
        pair = leaf_pair.previous #type: ActionPair # Pair before the double IDLE
        while pair.previous!=None:
            # update metrics
            if pair.human_action.is_passive():
                if not human_acted:
                    current_metrics["TimeEndHumanDuty"] -= 1
            else:
                human_acted = True
                current_metrics["HumanEffort"] += 1
                current_metrics["GlobalEffort"] += 1
            if not pair.robot_action.is_passive():
                current_metrics["GlobalEffort"] += 1
            
            is_cra_or_skip = False
            if pair.robot_action.name == "SKIP":
                is_cra_or_skip = True
            else:
                CRAs = pair.in_human_option.in_step.CRA
                if len(CRAs)>0:
                    for CRA in CRAs:
                        if CM.Action.are_similar(pair.robot_action, CRA):
                            is_cra_or_skip=True
                            break
            if not is_cra_or_skip:
                current_metrics["RiskConflict"] += 1

            # progress
            pair = pair.previous
        # set metrics
        leaf_pair.branch_metrics = current_metrics

def get_str_ranked_branches(ranked_leaves, robot=True):
    lines = []
    i=0
    while i<len(ranked_leaves):
        line = ""
        leaf = ranked_leaves[i] #type: Step
        rank = leaf.get_f_leaf().branch_rank_r if robot else leaf.get_f_leaf().branch_rank_h
        metrics=""
        for m in leaf.get_f_leaf().branch_metrics.values():
            metrics+=f"{m} "
        line = f"\t#{rank}: [{metrics[:-1]}]:({leaf.id})"
        while i+1<len(ranked_leaves) and ranked_leaves[i].get_f_leaf().branch_metrics == ranked_leaves[i+1].get_f_leaf().branch_metrics:
            line += f",({ranked_leaves[i+1].id})"
            i+=1
        i+=1
        lines.append(line)

    str = ""
    for l in lines[::-1]:
        str += l + "\n"
    return str

def sorting_branches(final_leaves: List[Step], criteria, is_robot=True):
    global G_CRITERIA
    G_CRITERIA = criteria # used in np.sort

    # leaves_copy = deepcopy(final_leaves)
    x = np.array( final_leaves )
    ranked_leaves = np.sort(x)
    
    # ranked_leaves = triFusion(final_leaves, criteria)
    
    # size = len(final_leaves)
    # quickSort(final_leaves, 0, size-1, criteria)
    # ranked_leaves = final_leaves

    # Set ranks of final leafs
    for i, ranked_leaf in enumerate(ranked_leaves):
        same = True
        for m in criteria:
            if ranked_leaf.get_f_leaf().branch_metrics[m[0]] != ranked_leaves[i-1].get_f_leaf().branch_metrics[m[0]]:
                same=False
                break
        if i>0 and same:
            if is_robot:
                ranked_leaf.get_f_leaf().branch_rank_r = ranked_leaves[i-1].get_f_leaf().branch_rank_r
            else:
                ranked_leaf.get_f_leaf().branch_rank_h = ranked_leaves[i-1].get_f_leaf().branch_rank_h
        else:
            if is_robot:
                ranked_leaf.get_f_leaf().branch_rank_r = i+1
            else:
                ranked_leaf.get_f_leaf().branch_rank_h = i+1


    return ranked_leaves


# Function to find the partition position
def partition(array, low, high, criteria):
 
    # choose the rightmost element as pivot
    pivot = array[high]
 
    # pointer for greater element
    i = low - 1
 
    # traverse through all elements
    # compare each element with pivot
    for j in range(low, high):
        if compare_metrics(array[j].get_f_leaf().branch_metrics, pivot.get_f_leaf().branch_metrics, criteria):
        # if array[j] <= pivot:
 
            # If element smaller than pivot is found
            # swap it with the greater element pointed by i
            i = i + 1
 
            # Swapping element at i with element at j
            (array[i], array[j]) = (array[j], array[i])
 
    # Swap the pivot element with the greater element specified by i
    (array[i + 1], array[high]) = (array[high], array[i + 1])
 
    # Return the position from where partition is done
    return i + 1
 
# function to perform quicksort
def quickSort(array, low, high, criteria):
    if low < high:
 
        # Find pivot element such that
        # element smaller than pivot are on the left
        # element greater than pivot are on the right
        pi = partition(array, low, high, criteria)
 
        # Recursive call on the left of pivot
        quickSort(array, low, pi - 1, criteria)
 
        # Recursive call on the right of pivot
        quickSort(array, pi + 1, high, criteria)

def triFusion(L, criteria):
    if len(L) == 1:
        return L
    else:
        return fusion( triFusion(L[:len(L)//2], criteria) , triFusion(L[len(L)//2:], criteria) , criteria)
    
def fusion(A:List[Step], B:List[Step], criteria):
    if len(A) == 0:
        return B
    elif len(B) == 0:
        return A
    elif compare_metrics(A[0].get_f_leaf().branch_metrics, B[0].get_f_leaf().branch_metrics, criteria):
        return [A[0]] + fusion( A[1:] , B , criteria)
    else:
        return [B[0]] + fusion( A , B[1:] , criteria)

def get_exec_prefs():
    prefs = {
        "human_min_work": [
            ("HumanEffort",         False),
            ("TimeEndHumanDuty",    False),
            ("GlobalEffort",        False),
            ("TimeTaskCompletion",  False),
        ],

        "human_free_early": [
            ("TimeEndHumanDuty",    False),
            ("HumanEffort",         False),
            ("GlobalEffort",        False),
            ("TimeTaskCompletion",  False),
        ],

        "task_end_early": [
            ("TimeTaskCompletion",  False),
            ("TimeEndHumanDuty",    False),
            ("HumanEffort",         False),
            ("GlobalEffort",        False),
        ],
    }

    return prefs

def esti_prefs_pairs():
    # prefs - esti
    pairs = {
        "tee_tee": ("task_end_early", "task_end_early"),
        "hmw_hmw": ("human_min_work", "human_min_work"),
        "hfe_hfe": ("human_free_early", "human_free_early"),
        
        "hmw_tee": ("human_min_work", "task_end_early"),
        "tee_hmw": ("task_end_early", "human_min_work"),
    }

    return pairs


##########
## TOOL ##
##########
def update_robot_choices(init_step: Step):
    
    # Recursively compute the metrics of each pair of a human option

    # Compute best choice of a step:
    # for each human option, compute metrics of all pairs 
    #   (either by computing best choice of below and take metrics, or either by reasoning on double passive, or if pair.next is final just take metrics), then compare them to find best choice. 
    # Compare the best choices of each HO and find the best choice of the step (to be used in upper steps)
    
    step_one = init_step.children[0]
    compute_best_rank_from_step_robot(step_one)

def update_human_choices(init_step: Step):
    step_one = init_step.children[0]
    compute_best_rank_from_step_human(step_one)

def compute_best_rank_from_step_robot(step: Step):
    best_step_pair = None
    for ho in step.human_options:
        best_pair = None
        for pair in ho.action_pairs:
            # check if pair is double passive, if so don't consider it as a potential best pair
            if pair.is_passive() and not pair.human_action.is_wait_turn() and not pair.robot_action.is_wait_turn():
                continue
            elif pair.next == []:
                continue
            elif pair.next[0].is_final():
                pair.best_rank_r = pair.next[0].branch_rank_r
            else:
                pair.best_rank_r = compute_best_rank_from_step_robot(pair.next[0].get_in_step())

            if pair.best_rank_r == None:
                continue
            if best_pair==None or pair.best_rank_r <= best_pair.best_rank_r:
                best_pair = pair    
            ho.best_robot_pair = best_pair

        if ho.best_robot_pair==None:
            continue
        if best_step_pair==None or ho.best_robot_pair.best_rank_r <= best_step_pair.best_rank_r:
            best_step_pair = ho.best_robot_pair
    step.best_robot_pair = best_step_pair

    result = best_step_pair.best_rank_r if best_step_pair!=None else None
    return result

def compute_best_rank_from_step_human(step: Step):
    best_step_pair = None
    for ho in step.human_options:
        best_pair = None
        for pair in ho.action_pairs:
            # check if pair is double passive, if so don't consider it as a potential best pair
            if pair.is_passive() and not pair.human_action.is_wait_turn() and not pair.robot_action.is_wait_turn():
                continue
            elif pair.next == []:
                continue
            elif pair.next[0].is_final():
                pair.best_rank_h = pair.next[0].branch_rank_h
            else:
                pair.best_rank_h = compute_best_rank_from_step_human(pair.next[0].get_in_step())

            if pair.best_rank_h == None:
                continue
            if best_pair==None or pair.best_rank_h <= best_pair.best_rank_h:
                best_pair = pair    
            ho.best_human_pair = best_pair

        if ho.best_human_pair==None:
            continue
        if best_step_pair==None or ho.best_human_pair.best_rank_h <= best_step_pair.best_rank_h:
            best_step_pair = ho.best_human_pair
    step.best_human_pair = best_step_pair

    result = best_step_pair.best_rank_h if best_step_pair!=None else None
    return result

def compare_metrics(m1, m2, criteria):
    """ Returns True if m1 if better than m2 """
    for m,maxi in criteria:
        if m1[m] < m2[m]:
            return not maxi
        elif m1[m] > m2[m]:
            return maxi
    # If equal
    return True


############
## HELPER ##
############
def check_list(list, cond):
    """
    Returns None if the given condition (cond) is False for every element of the list
    Otherwise, return the first element for which the condition is True
    """
    for x in list:
        if cond(x):
            return x


###########
## PRINT ##
###########
def show_solution(init_step: Step):
    lg.info(f"\n### SOLUTION ### [domain:{CM.g_domain_name}]")
    lg.info(RenderTree(init_step))
    for s in init_step.descendants:
        if not s.is_leaf:
            lg.info(f"{s.str(last_line=False)}")
    lg.info(f"Number of branches: {len(init_step.get_final_leaves())}")


#############
## DUMPING ##
#############
def dumping_solution(init_step: Step, tt_explore = False):
    lg.info("Dumping solution...")
    s_t = time.time()
    sys.setrecursionlimit(100000)


    file_name = "dom_n_sol.p"
    if tt_explore:
        file_name = file_name[:-2] + "_tt.p" 

    dill.dump( (CM.g_domain_name, init_step) , open(CM.path + file_name, "wb"))
    lg.info("Solution dumped! - %.2fs" %(time.time()-s_t))

    f = open(CM.path + "dom_name.p", "w")
    f.write(f"domain_name: \"{CM.g_domain_name}\"")
    f.close()

################## DUMPING ##################

# Step :        <id>, [<pair>]
# Pair :        <HA_id>, <HA>, <RA_id>, <RA>, <best_reachable_rank>, <step>
# Final Pair :  <HA_id>, <HA>, <RA_id>, <RA>, <best_reachable_rank>, <branch_metrics>, <final_state>

def update_sol_dic(step: Step, curr_step_dict):
    curr_step_dict['id'] = step.id

    curr_step_dict['pair'] = [] 
    for p in step.get_pairs():
        curr_step_dict['pair'].append({ 
            'HA_id':        p.human_action.id, 
            'HA':           f"{p.human_action.name}{list(p.human_action.parameters)}", 
            'RA_id':        p.robot_action.id, 
            'RA':           f"{p.robot_action.name}{list(p.robot_action.parameters)}", 
            'best_rank':    -1,
        })

        if p.next != []:
            curr_step_dict['pair'][-1]['step'] = {}
            update_sol_dic(p.next[0].get_in_step(), curr_step_dict['pair'][-1]['step'])
        elif p.is_final():
            curr_step_dict['pair'][-1]['metrics'] = "-1"
            curr_step_dict['pair'][-1]['final_state'] = convert_state_to_dict(p.end_agents.state)
        elif p.is_passive():
            continue # do nothing, double wait step
        else:
            raise Exception("Shouldn't happen...")

def convert_list_to_dict(d):

    for k in d:
        if isinstance(d[k], list):
            l = d[k]
            d[k] = {}
            for e in l:
                d[k][e] = {}
        elif isinstance(d[k], dict):
            convert_list_to_dict(d[k])



def convert_state_to_dict(state):

    state_dict = {}

    for f in state.fluents:
        state_dict[f] = getattr(state, f)

    convert_list_to_dict(state_dict)

    return state_dict

def xml_dump(begin_step, tt_explore = False):
    print("dumping... ")
    start_time = time.time()

    # Could be great to add initial_state and initial_agenda in it, solution would be self sufficient, problem included
    sol_dic = {'sol':{'domain_name':CM.g_domain_name, 'initial_state':convert_state_to_dict(CM.g_static_agents.state), 'initial_agendas': {}, 'begin_step':{}}}
    update_sol_dic(begin_step, sol_dic['sol']['begin_step'])

    f = open(CM.path + 'solution.xml', 'w')
    f.write(simplexml.dumps(sol_dic))
    f.close()

    end_time = time.time()
    print(f"solution dumped in {end_time-start_time} s.")

################## LOADING ##################

def convert_dict_to_list(d):

    if not isinstance(d, dict):
        return d

    # check if a list 
    l = []
    for f in d:
        if d[f] != {}:
            d[f] = convert_dict_to_list(d[f])
        else:
            l.append(f)

    if l != []:
        return l
    else:
        return d


def convert_dict_to_state(d):
    initial_state = CM.State("init")

    d = convert_dict_to_list(d)

    for f in d:
        initial_state.create_dyn_fluent(f, d[f])

    return initial_state



def get_name_and_parameters(full_action_name):
    i_find = full_action_name.find('[')
    name = full_action_name[:i_find]
    raw_params = full_action_name[i_find+1:-1].split(",")
    parameters = []
    for para in raw_params:
        parameters.append(para.replace("'", ""))
    return name, parameters


def convert_step_dict_to_Step(dict_step, from_step, from_pair):

    step = Step(parent=from_step)

    if isinstance(dict_step['pair'], list):
        dict_pairs = dict_step['pair']
    else:
        dict_pairs = [dict_step['pair']]
    final_step = len(dict_pairs)==1 and 'metrics' in dict_pairs[0]
    action_pairs = []
    for p in dict_pairs:
        r_name, r_parameters = get_name_and_parameters(p["RA"])
        RA = CM.Action()
        RA.minimal_init(p["RA_id"], r_name, r_parameters, "R")

        h_name, h_parameters = get_name_and_parameters(p["HA"])
        HA = CM.Action()
        HA.minimal_init(p["HA_id"], h_name, h_parameters, "H")

        action_pair = ActionPair(HA, RA, None)
        action_pairs.append(action_pair)

        if final_step:
            # read metrics
            action_pair.branch_metrics = p['metrics']
            # action_pair.end_agents.state = p['final_state']
        elif action_pair.is_passive() and not action_pair.is_begin():
            continue
        else:
            # keep exploring
            convert_step_dict_to_Step(p["step"], step, action_pair)

    human_options = arrange_pairs_in_HumanOption(action_pairs)
    step.init(human_options, from_pair)
    step.id = dict_step['id']

    return step

def xml_load():
    f = open(CM.path + "solution.xml", 'r')
    line = f.readline()
    if line=='<?xml version="1.0"?>\n':
        content = f.read()
        f.close()
        content = content.replace(' ', '')
        content = content.replace('\t', '')
        content = content.replace('\n', '')
        head = '<?xml version="1.0"?>'
        content = head + content
    else:
        content = line

    dict_solution = simplexml.loads(content)
    
    domain_name = dict_solution['sol']['domain_name']
    initial_state = convert_dict_to_state(dict_solution['sol']['initial_state'])
    begin_step = convert_step_dict_to_Step(dict_solution['sol']['begin_step'], None, None)

    return domain_name, initial_state, begin_step
