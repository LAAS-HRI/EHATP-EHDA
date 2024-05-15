#!/usr/bin/env python3
import sys
import os
from copy import deepcopy
import time


import CommonModule as CM
import ConcurrentModule as ConM
import solution_checker

import cProfile
import pstats


######################################################
################### Primitive tasks ##################
######################################################

## operator - move to table - to move to the other table ##
## context for the agent to the table is required before moving close to it
def o_move_precond(state, agent, place_i, place_j):
    return ( agent == "H" 
            and state.agent_in_context[agent] == place_i 
            and state.agent_at[agent] == place_i) 
def o_move_effects(state, agent, place_i, place_j):
    state.agent_at[agent] = place_j
    state.agent_in_context[agent] = place_j
o_move = CM.Operator("move", pre_cond=o_move_precond, effects=o_move_effects)


def o_get_ingredient_precond(state, agent):
    return ( agent == "H"
            and state.agent_at[agent] == "pantry" 
            and state.ingredient_at["ingredient"] == "pantry")

def o_get_ingredient_effects(state, agent):
    state.ingredient_at["ingredient"] = agent

o_get_ingredient = CM.Operator("get_ingredient", pre_cond=o_get_ingredient_precond, effects=o_get_ingredient_effects)


def o_put_ingredient_precond(state, agent):
    return ( agent == "H"
            and state.agent_at[agent] == "kitchen" 
            and state.ingredient_at["ingredient"] == agent
            and state.boiling["vegetable"] == True)
def o_put_ingredient_effects(state, agent):
    state.ingredient_at["ingredient"] = "vegetable"    

o_put_ingredient = CM.Operator("put_ingredient", pre_cond=o_put_ingredient_precond, effects=o_put_ingredient_effects)


def o_cut_precond(state, agent):
    return ( not state.cut["vegetable"] ) 
def o_cut_effects(state, agent):
    state.cut["vegetable"] = True
o_cut = CM.Operator("cut", pre_cond=o_cut_precond, effects=o_cut_effects)

def o_wash_precond(state, agent):
    return ( (not state.washed["vegetable"])
            and state.cut["vegetable"] == True)
def o_wash_effects(state, agent):
    state.washed["vegetable"] = True
o_wash = CM.Operator("wash", pre_cond=o_wash_precond, effects=o_wash_effects)

def o_seasoning_precond(state, agent):
    return ( (not state.seasoned["vegetable"])
            and state.washed["vegetable"]) 
def o_seasoning_effects(state, agent):
    state.seasoned["vegetable"] = True
o_seasoning = CM.Operator("seasoning", pre_cond=o_seasoning_precond, effects=o_seasoning_effects)


def o_put_on_stove_precond(state, agent):
    return ( state.washed["vegetable"]
            and not state.boiling["vegetable"] ) 
def o_put_on_stove_effects(state, agent):
    state.boiling["vegetable"] = True
o_put_on_stove = CM.Operator("put_on_stove", pre_cond=o_put_on_stove_precond, effects=o_put_on_stove_effects)

# auxiliary action
def o_aux_done_cooking_precond(state, agent):
    return ((not food_is_ready(state)) and state.seasoned["vegetable"] 
            and state.ingredient_at["ingredient"] == "vegetable")
def o_aux_done_cooking_effects(state, agent):
    state.cooking_done["food_ready"] = True
o_aux_done_cooking = CM.Operator("aux_done_cooking", pre_cond=o_aux_done_cooking_precond, effects=o_aux_done_cooking_effects)

## communicate the inspected status of the cube
def o_get_effect(state, agent):        
    return state.seasoned["vegetable"]
def o_communicate_precond(state, agent):
    # if(agent != "R"):
    return True
def o_communicate_effects(state, agent):
    True == True
o_communicate = CM.Operator("communicate_status_of_seasoned", pre_cond=o_communicate_precond, effects=o_communicate_effects, get_effect=o_get_effect)


common_ops = [o_cut, o_wash, o_communicate]
robot_ops = common_ops + [o_seasoning, o_put_on_stove]
human_ops = common_ops + [o_move, o_get_ingredient, o_put_ingredient, o_aux_done_cooking]


######################################################
################### Abstract Tasks ###################
######################################################

## Communicate ##
def m_Communicate_precond(state, agent):    
    return True
    
def m_Communicate_decomp(state, agent):
    multi_subtasks = []
    multi_subtasks.append([("communicate_status_of_seasoned", )])    
    return multi_subtasks
m_Communicate = CM.Method("Communicate", pre_cond=m_Communicate_precond, multi_decomp=m_Communicate_decomp)


# new main abstract task - Prepare_Dinner
def m_Prepare_Dinner_donecond(state, agent):
    return state.cooking_done["food_ready"]

def m_Prepare_Dinner_precond(state, agent):
    return not state.cooking_done["food_ready"]

# def m_Prepare_Dinner_multi_decomp(state, agent):
#     multi_subtasks = []
#     # M1 - cut and wash
#     # if present at stove's location 
#     if True: #if human acts and nothing has been done, human is near stove
#         multi_subtasks.append([("Cut_n_Wash",), ("Bring_Ingredient_From_Pantry", ), ("Put_Ingredient", ), ("Prepare_Dinner", )])
#     elif True: # execute the dummy action in the last for human
#         multi_subtasks.append([("Done_Cooking", ) ])
#     elif True: # if human has done -- aux_done_cooking
#         multi_subtasks = []

# m_Prepare_Dinner_h1 = CM.Method("Prepare_Dinner", pre_cond=m_Prepare_Dinner_precond, done_cond=m_Prepare_Dinner_donecond, multi_decomp=m_Prepare_Dinner_multi_decomp)


def m_Prepare_Dinner_multi_decomp_h2(state, agent):
    multi_subtasks = []
    if state.agent_at[agent] == "kitchen" and state.ingredient_at["ingredient"] == "pantry":
        multi_subtasks.append([("Bring_Ingredient_From_Pantry", ), ("Put_Ingredient", ), ("Prepare_Dinner", )])
    elif state.seasoned["vegetable"] and state.ingredient_at["ingredient"] == "vegetable":
        multi_subtasks.append([("Done_Cooking", ), ("Prepare_Dinner", )])    
    return multi_subtasks    
m_Prepare_Dinner_h2 = CM.Method("Prepare_Dinner", pre_cond=m_Prepare_Dinner_precond, done_cond=m_Prepare_Dinner_donecond, multi_decomp=m_Prepare_Dinner_multi_decomp_h2)


################
def m_Bring_Ingredient_From_Pantry_precond(state, agent):
    return not food_is_ready(state) and state.ingredient_at["ingredient"] == "pantry"   

def m_Bring_Ingredient_From_Pantry_multi_decomp(state, agent):
    multi_subtasks = []
    if state.agent_at[agent] == "kitchen":
        multi_subtasks.append([("move", "kitchen", "pantry"), ("get_ingredient", ), ("move", "pantry", "kitchen")])
    return multi_subtasks
m_Bring_Ingredient_From_Pantry_h1 = CM.Method("Bring_Ingredient_From_Pantry", pre_cond=m_Bring_Ingredient_From_Pantry_precond, multi_decomp=m_Bring_Ingredient_From_Pantry_multi_decomp)

################
def m_Put_Ingredient_precond(state, agent):
    # the pan must be on stove and is hot and food is not ready 
    return not food_is_ready(state)    

def m_Put_Ingredient_multi_decomp(state, agent):
    multi_subtasks = []
    if state.agent_at[agent] == "kitchen" and state.ingredient_at["ingredient"] == agent:
        multi_subtasks.append([("put_ingredient", ) ])
    return multi_subtasks
m_Put_Ingredient_h1 = CM.Method("Put_Ingredient", pre_cond=m_Put_Ingredient_precond, multi_decomp=m_Put_Ingredient_multi_decomp)

def m_Prepare_Dinner_multi_decomp_r1(state, agent):
    multi_subtasks = []
    if state.agent_at[agent] == "kitchen" and not state.cut["vegetable"]:
        multi_subtasks.append([("Cut_n_Wash",), ("put_on_stove", ), ("seasoning", ), ("Prepare_Dinner", )])
    elif state.agent_at[agent] == "kitchen" and not state.boiling["vegetable"]:
        multi_subtasks.append([("put_on_stove", ), ("seasoning", ), ("Prepare_Dinner", )])
    elif state.agent_at[agent] == "kitchen" and not state.seasoned["vegetable"]:
        multi_subtasks.append([("seasoning", ), ("Prepare_Dinner", )])
    ##        
    return multi_subtasks
m_Prepare_Dinner_r1 = CM.Method("Prepare_Dinner", pre_cond=m_Prepare_Dinner_precond, done_cond=m_Prepare_Dinner_donecond, multi_decomp=m_Prepare_Dinner_multi_decomp_r1)

# def m_Prepare_Dinner_multi_decomp_r2(state, agent):
#     multi_subtasks = []
#     if True: #if human acts and nothing has been done, human is near stove
#         multi_subtasks.append([("Cut_n_Wash",), ("seasoning", ), ("put_on_stove", ), ("Prepare_Dinner", )])
#     elif True: # if human has done -- aux_done_cooking
#         multi_subtasks = []

# m_Prepare_Dinner_r2 = CM.Method("Prepare_Dinner", pre_cond=m_Prepare_Dinner_precond, done_cond=m_Prepare_Dinner_donecond, multi_decomp=m_Prepare_Dinner_multi_decomp_r2)


def m_Done_Cooking_precond(state, agent):
    # whether the curry is seasoned and pan is on the stove
    cond = ((not food_is_ready(state)) and state.seasoned["vegetable"] 
            and state.ingredient_at["ingredient"] == "vegetable")
    return cond    

def m_Done_Cooking_multi_decomp(state, agent):
    multi_subtasks = []
    if not food_is_ready(state):
        multi_subtasks.append([("aux_done_cooking",) ])
    return multi_subtasks
m_Done_Cooking_h3 = CM.Method("Done_Cooking", pre_cond=m_Done_Cooking_precond, multi_decomp=m_Done_Cooking_multi_decomp)


############## common abstract task ###########
def m_Cut_n_Wash_donecond(state, agent):
    # is the vegetable cut and washed
    return state.cut["vegetable"] and state.washed["vegetable"]

def m_Cut_n_Wash_precond(state, agent):
    return (not state.cut["vegetable"] or not state.washed["vegetable"])

def m_Cut_n_Wash_multi_decomp(state, agent):
    multi_subtasks = []
    if state.agent_at[agent] == "kitchen" and not state.cut["vegetable"]: 
        multi_subtasks.append([("cut",), ("wash", ), ("Cut_n_Wash",)])
    elif state.agent_at[agent] == "kitchen" and not state.washed["vegetable"]:
        multi_subtasks.append([("wash", ), ("Cut_n_Wash",)])
    return multi_subtasks
m_Cut_n_Wash_comm = CM.Method("Cut_n_Wash", pre_cond=m_Cut_n_Wash_precond, done_cond=m_Cut_n_Wash_donecond, multi_decomp=m_Cut_n_Wash_multi_decomp)


# m_Pick_n_place_ll,
common_methods = [m_Cut_n_Wash_comm, m_Communicate]
robot_methods = common_methods + [m_Prepare_Dinner_r1]
human_methods = common_methods + [m_Prepare_Dinner_h2, m_Done_Cooking_h3, m_Bring_Ingredient_From_Pantry_h1, m_Put_Ingredient_h1]

######################################################
###################### Triggers ######################
######################################################

common_triggers = []
robot_triggers = common_triggers + []
human_triggers = common_triggers + []


######################################################
###################### Helpers #######################
######################################################
def is_robot(agent):
    return agent=="R"

def goal_condition(state):
    return food_is_ready(state)

######################################################
################## Goal Condition ####################
######################################################
def food_is_ready(state):
    if state.cooking_done["food_ready"]:
        return True
    return False


######################################################
######################## MAIN ########################
######################################################

def initDomain():
    # Set domain name
    domain_name = os.path.basename(__file__)[:-3] # filename minus ".py"
    CM.set_domain_name(domain_name)  

    # Initial state
    initial_state = CM.State("init")

    # Static properties
    initial_state.create_static_fluent("self_name", "None")
    initial_state.create_static_fluent("stove_at", {
        "stove" : "kitchen"
    })
           

    #################################################################
    ### primitive variables and their values in the initial state ###
    #################################################################
    initial_state.create_dyn_fluent("cooking_done", { 
        "food_ready" : False 
    })

    initial_state.create_dyn_fluent("washed", { 
        "vegetable" : False 
    })

    initial_state.create_dyn_fluent("cut", { 
        "vegetable" : False 
    })

    initial_state.create_dyn_fluent("seasoned", { 
        "vegetable" : False 
    })

    initial_state.create_dyn_fluent("boiling", { 
        "vegetable" : False 
    })

    initial_state.create_dyn_fluent("ingredient_at", {
        "ingredient" : "pantry" ## other values in hand of the human or put in the vegetable
    })
    
    initial_state.create_dyn_fluent("agent_in_context", {  
        "H" : "kitchen",
        "R" : "kitchen"
    })

    initial_state.create_dyn_fluent("agent_at", { 
        "H" : "kitchen",
        "R" : "kitchen"
    })

    ## observability -- the variables not appearing here are all visible in the environment ##
    initial_state.create_static_fluent("observability_washed_vegetable", {         
        "washed" : True
    })

    initial_state.create_static_fluent("observability_seasoned_vegetable", {         
        "seasoned" : False
    })

    

    CM.set_state(initial_state)

    # Robot init #
    CM.declare_operators("R", robot_ops)
    CM.declare_methods("R", robot_methods)
    CM.add_tasks("R", [("Prepare_Dinner",)])

    # Human init #
    CM.declare_operators("H", human_ops)
    CM.declare_methods("H", human_methods)
    CM.add_tasks("H", [("Prepare_Dinner",)])

    CM.set_starting_agent("H")

# test function -- pass an appropriate file path later
def print_relevant_solution_state_details_nofiles(sol):    
    print("")
    for des in sol.descendants:
        print ("\n\nDescendent state details (code = " + str(des) + ")")
        for each_pair in des.from_pair.next:
            print("\nAction pair: " + str(each_pair))
            print("\nThe real designated state (state that the robot knows)")
            CM.print_state(each_pair.end_agents.state)
            if(len(each_pair.possible_worlds_for_h) > 0):
                print("\nOther possible states w.r.t. this action pair (human assumes to be a possible true state)")
            counter = 1
            for each_world in each_pair.possible_worlds_for_h:
                print("\nPossible world number - " + str(counter) + "\n")
                CM.print_state(each_world.state)
                counter += 1
    print("Back in console.")


def main(tt_explore, allowed_to_signal):
    goal_test = [False, ""]
    sys.setrecursionlimit(100000)
    initDomain()
    # pr = cProfile.Profile()
    # pr.enable()

    s_t = time.time()

    # NOTE: for now allowing the robot to choose PASS first when using AND/OR search will not work
    # sol = ConM.explore(tt_explore, allowed_to_signal)
    sol = ConM.explore_ANDOR(tt_explore, allowed_to_signal, goal_test)
    
    print("time to explore: %.2fs" %(time.time()-s_t)) 
    print(f"Number of leaves: {len(sol.get_final_leaves(tt_explore))}")
    print(f"Nb states = {sol.get_nb_states()}")
    
    # pr.disable()
    # stats = pstats.Stats(pr).sort_stats("tottime")
    # stats.dump_stats(filename="profiling.prof")

    # print_relevant_solution_state_details(sol)

    return sol

if __name__ == "__main__":

    #shashank
    tt_explore = True
    allowed_to_signal = False

    if len(sys.argv) > 1 and sys.argv[1] == "tt":
        tt_explore = True
    
    # NOTE: for now allowing the robot to choose PASS first whne using AND/OR search may not work
    sol = main(tt_explore, allowed_to_signal)

    solution_checker.check_solution(sol, goal_condition)

    # ConM.simplify_solution(sol)

    ConM.dumping_solution(sol, tt_explore)