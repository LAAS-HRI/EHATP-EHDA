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
################### Rules for SA #####################
######################################################

## pass the designated state, assess what human can observe in their current context
## return "w_the_possible_state_to_keep" as "to keep" state if values of the variables that are observed by human in 
## state and w_the_possible_state_to_keep are the same  
## the idea is to remove all possible states from human mental model of which human is uncertain about 
## such that Human can marley discard this state by visualizing the designated world 
def applyRulesForSituationAssessment(state, w_the_possible_state_to_keep):
    
    # state_post_sa = None #appropriate ds?
    
    # FORMAT === {antecedent_i} => consequent

    # E.g., if human is in the context of table and present at the table
    # they will assess all cubes orientation on the table
    # Note that we will specify only a single consequent that is OBSERVABLE w.r.t. an antecedent (i.e. a formula)
    # these rules will be "stratified" -- divided into multiple strata -- could be interesting while writing 
    
    if state.agent_in_context["H"]["table_context"] == "table" and state.agent_at["H"]["agent_at_table"] == "table":
        ######
        """
        for cube_name in state.cube_at_table:
            if (state.cube_at_table[cube_name]["at_table"] == "table"):
                if(w_the_possible_state_to_keep.cube_at_table[cube_name]["at_table"] != "table"):
                    return None

        for cube_name in state.color_cubes:
            if (state.holding["R"] == cube_name):
                if (w_the_possible_state_to_keep.holding["R"] != cube_name):
                    return None
                # w_the_possible_state_to_keep.color_cubes[cube_name]["on"] = []
                # w_the_possible_state_to_keep.cube_at_table[cube_name]["at_table"] = None
        """

        # focus: on at_table(cube) fact only:
        for cube in state.color_cubes:
            if (state.cube_at_table[cube]["at_table"] != 
                w_the_possible_state_to_keep.cube_at_table[cube]["at_table"]):
                return None
        
        # focus: on "cube on something" fact only:
        for cube in state.color_cubes:
            if (state.color_cubes[cube]["on"] != 
                w_the_possible_state_to_keep.color_cubes[cube]["on"]):
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
        # the loop below is not verified and will not be called as of now
        for loc in state.solution:
            if state.locations[loc] != None:
                w_the_possible_state_to_keep.color_cubes[state.locations[loc]]["on"] = []
                w_the_possible_state_to_keep.cube_at_table[state.locations[loc]]["at_table"] = None
                w_the_possible_state_to_keep.locations[loc] = state.locations[loc]
        ######
        """

        # similarly if a cube is already placed in the solution stack in "table"
        # human will be able to see it as well
        # what human cannot see is cubes inspected by the robot when they were not in the right context

    return "keep"  
rules_for_situation_assessment = CM.RulesForSA("get_sa_done_wrt_this_designated_state", rule_antecedent_consequent = applyRulesForSituationAssessment)



######################################################
################### Primitive tasks ##################
######################################################

## operator - take turn - (for facing towards another table and moving to that table) ##
## taking turn changes the context for the agent from one table to another but it remains situated at the former
def o_turn_precond(state, agent, table_i, table_j):
    return ( agent == "H" 
            and state.agent_in_context[agent]["table_context"] == table_i) 
def o_turn_effects(state, agent, table_i, table_j):
    state.agent_in_context[agent]["table_context"] = table_j
o_turn = CM.Operator("change_table_context", pre_cond=o_turn_precond, effects=o_turn_effects)

## operator - move to table - to move to the other table ##
## context for the agent to the table is required before moving close to it
def o_move_precond(state, agent, table_i, table_j):
    return ( agent == "H" 
            and state.agent_in_context[agent]["table_context"] == table_j
            and state.agent_at[agent]["agent_at_table"] == table_i) 
def o_move_effects(state, agent, table_i, table_j):
    state.agent_at[agent]["agent_at_table"] = table_j
o_move = CM.Operator("move_to_table", pre_cond=o_move_precond, effects=o_move_effects)

## inspect operator ##
# inspect a cube/location -- a cube can be inspected when it is placed in the stack at appropriate position 
# and there is nothing on top of it.
def o_inspect_donecond(state, agent, cube):
    return (state.inspected_cube_to_place[cube]["inspected"] == True)
def o_inspect_precond(state, agent, cube): 
    return ( 
        # agent == "R" and 
        state.inspected_cube_to_place[cube]["inspected"] == False) 
    # target_supports_ok(state, place_to) and target_free(state, place_to)
def o_inspect_effects(state, agent, cube):
    state.inspected_cube_to_place[cube]["inspected"] = True
o_inspect = CM.Operator("inspect_cube", done_cond=o_inspect_donecond, pre_cond=o_inspect_precond, effects=o_inspect_effects)


## pick ##
# Picks a cube from a side
def o_pick_precond(state, agent, cube_name):
    return (state.agent_at[agent]["agent_at_table"] == state.cube_at_table[cube_name]["at_table"] 
            and cube_reachable_by(state, cube_name, agent))
def o_pick_effects(state, agent, cube_name):
    state.color_cubes[cube_name]["on"] = []
    state.cube_at_table[cube_name]["at_table"] = None
    state.holding[agent] = cube_name
    complete_color_cubes_info(state)
o_pick = CM.Operator("pick", pre_cond=o_pick_precond, effects=o_pick_effects)

## place operator ## # Places the cube held in the stack
def o_place_precond(state, agent, place_to, cube_name):
    print("placed ...")
    return (state.holding[agent]==cube_name 
                and state.agent_at[agent]["agent_at_table"] == "table"
                and state.color_cubes[cube_name]["color"] in state.solution[place_to]["colors"] 
                and target_supports_ok(state, place_to) 
                and target_free(state, place_to)
                and inspect_target_supports(state, place_to) == []
            )
            # and state.inspected_place_to[place_to]["inspected"] == True) 
def o_place_effects(state, agent, place_to, cube_name):
    state.locations[place_to] = cube_name
    state.holding[agent] = None
    state.cube_at_table[cube_name]["at_table"] = "table"
o_place = CM.Operator("place", pre_cond=o_place_precond, effects=o_place_effects)

## drop ##
# Places the cube held back in a side
def o_drop_precond(state, agent, cube_name, side):
    if state.holding[agent]==cube_name:
        if is_robot(agent):
            return side in ["R", "C"]
        else:
            return side in ["H", "C"]
    return False
def o_drop_effects(state, agent, cube_name, side):
    state.color_cubes[cube_name]["on"] = [side]
    state.holding[agent] = None
    state.cube_at_table[cube_name]["at_table"] = state.agent_in_context[agent]["table_context"]
o_drop = CM.Operator("drop", pre_cond=o_drop_precond, effects=o_drop_effects)


## communicate the inspected status of the cube
def o_get_effect(state, agent, cube_name):    
    if (state.inspected_cube_to_place[cube_name[0]]["inspected"] == True):
        return True
    return False

def o_communicate_precond(state, agent, cube_name):
    # if(agent != "R"):
    #     return False
    if (state.agent_at["H"]["agent_at_table"] == "table" and state.agent_at["R"]["agent_at_table"] == "table"):
        # if state.inspected_cube_to_place[cube_name]["inspected"] == True:
        #     return True
        # else:
        return True
    else:
        return False
def o_communicate_effects(state, agent, cube_name):
    if state.inspected_cube_to_place[cube_name]["inspected"] == True:
        state.inspected_cube_to_place[cube_name]["inspected"] == True 
    else:    
        state.inspected_cube_to_place[cube_name]["inspected"] == False 
        # return just the effect --- probably no precondition required
o_communicate = CM.Operator("communicate_inspected_status_of_cube", pre_cond=o_communicate_precond, effects=o_communicate_effects, get_effect=o_get_effect)


common_ops = [o_communicate, o_inspect, o_pick, o_place, o_drop]
robot_ops = common_ops + []
human_ops = common_ops + [o_turn, o_move]


######################################################
################### Abstract Tasks ###################
######################################################

## Communicate ##
## communicate whether the cube is inspected or not
## Stack ##
def m_Communicate_precond(state, agent, cube_name):
    # if (state.agent_at["H"]["agent_at_table"] == "table" and state.agent_at["R"]["agent_at_table"] == "table"):
    #     if state.inspected_cube_to_place[cube_name]["inspected"] == True:
    #         return True
    #     else:
    #         return False
    # else:
    return True
    
def m_Communicate_decomp(state, agent, cube_name):
    multi_subtasks = []
    multi_subtasks.append([("communicate_inspected_status_of_cube", cube_name)])    
    return multi_subtasks
m_Communicate = CM.Method("Communicate", pre_cond=m_Communicate_precond, multi_decomp=m_Communicate_decomp)


## Stack ##
def m_Stack_donecond(state, agent):
    return goal_reached(state)

def m_Stack_precond(state, agent):
    for cube in state.color_cubes:
        if (state.agent_at[agent]["agent_at_table"] == state.cube_at_table[cube]["at_table"]
        and cube_side_reachable_by(state, cube, agent) 
        and cube_can_be_placed(state, cube)):
            return True
    return False    

def m_Stack_multi_decomp(state, agent):
    multi_subtasks = []
    for cube_name in state.color_cubes:
        if cube_side_reachable_by(state, cube_name, agent) and cube_can_be_placed(state, cube_name):
            if cube_reachable_by(state, cube_name, agent):
                multi_subtasks.append([ ("pick", cube_name), ("Place", cube_name), ("Stack",) ])
            else: # Unstack
                multi_subtasks.append([ ("Unstack", cube_name), ("Stack",) ])

    if multi_subtasks==[]:
        raise Exception("WeirdStack")
        multi_subtasks=[[]] # Done
    return multi_subtasks
m_Stack = CM.Method("Stack", pre_cond=m_Stack_precond, done_cond=m_Stack_donecond, multi_decomp=m_Stack_multi_decomp)


## Stack ##
def m_Stack_far_precond(state, agent):
    for cube in state.color_cubes:
        if (cube_can_be_placed(state, cube) 
            and cube_side_reachable_by(state, cube, agent)
            and state.agent_at[agent]["agent_at_table"] != state.cube_at_table[cube]["at_table"]):
            return True
    return False    

def m_Stack_far_multi_decomp(state, agent):
    multi_subtasks = []
    for cube in state.color_cubes:
        if (cube_can_be_placed(state, cube) 
            and state.agent_at[agent]["agent_at_table"] != state.cube_at_table[cube]["at_table"]):
                multi_subtasks.append([ ("Pick", cube), ("Place", cube), ("Stack",) ])
    
    return multi_subtasks
m_Stack_far = CM.Method("Stack", pre_cond=m_Stack_far_precond, multi_decomp=m_Stack_far_multi_decomp)


## Unstack
def m_Unstack_decomp(state, agent, cube_name):
    cube_to_unstack = cube_name

    while state.color_cubes[cube_to_unstack]["below"] != None:
        cube_to_unstack = state.color_cubes[cube_to_unstack]["below"]

    return [("pick", cube_to_unstack), ("Place", cube_to_unstack)]
m_Unstack = CM.Method("Unstack", decomp=m_Unstack_decomp)

## Pick from far ##
## Tries to pick the cube relevant for the stack
def m_Pick_far_precond(state, agent, cube_name):
    return (state.agent_at[agent]["agent_at_table"] != state.cube_at_table[cube_name]["at_table"]
            and cube_side_reachable_by(state, cube_name, agent))
def m_Pick_far_multi_decomp(state, agent, cube_name):
    multi_subtasks = []

    # Check if the agent can place in the stack, if so find and return corresponding PT, else drop the cube back on table
    if state.agent_in_context[agent]["table_context"] == state.cube_at_table[cube_name]["at_table"]:
        multi_subtasks.append([("move_to_table", state.cube_at_table[cube_name]["at_table"], state.agent_in_context[agent]["table_context"]), 
                               ("pick", cube_name)])
    else:
        multi_subtasks.append([ ("change_table_context", state.agent_at[agent]["agent_at_table"], state.cube_at_table[cube_name]["at_table"]), 
                               ("move_to_table", state.agent_at[agent]["agent_at_table"], state.cube_at_table[cube_name]["at_table"]), 
                               ("pick", cube_name)])

    return multi_subtasks
m_Pick_far = CM.Method("Pick", pre_cond=m_Pick_far_precond, multi_decomp=m_Pick_far_multi_decomp)


# "o_get_precond or in other words o_get_precond_for_comm" 
# The main idea is to retrieve all the preconditions of "m" that do not hold in the possible world(s)
# Here is a hack: I already know that communication is required for knowing whether a relevant cube is inspected
def o_get_precond(state, agent, cube_name):    
    if cube_can_be_placed(state, cube_name):
        for l in state.solution:
            if (state.color_cubes[cube_name]["color"] in state.solution[l]["colors"] 
                and target_supports_ok(state, l) 
                and target_free(state, l)):
                    return inspect_target_supports(state, l)

## Place - AT ##
# Tries to place the cube in the stack, otherwise drop it on the table
def m_Place_precond(state, agent, cube_name):
    flag_in_context = state.holding[agent]==cube_name and state.agent_at[agent]["agent_at_table"] == "table"
    # Check if the agent can place in the stack, if so find and return corresponding PT, else drop the cube back on thetable
    if not flag_in_context:
        return False
    elif cube_can_be_placed(state, cube_name):
        for l in state.solution:
            if (state.color_cubes[cube_name]["color"] in state.solution[l]["colors"] 
                and target_supports_ok(state, l) 
                and target_free(state, l)
                and inspect_target_supports(state, l) == []):
                return True
    return False

def m_Place_multi_decomp(state, agent, cube_name):
    multi_subtasks = []
    if cube_can_be_placed(state, cube_name):
        for l in state.solution:
            if (state.color_cubes[cube_name]["color"] in state.solution[l]["colors"] 
                and target_supports_ok(state, l) 
                and target_free(state, l) 
                ):                
                if inspect_target_supports(state, l) == []:
                    multi_subtasks.append([ ("place", l, cube_name), ("inspect_cube", cube_name) ])                 
    else:
        multi_subtasks.append([ ("Drop", cube_name) ])

    if multi_subtasks==[]:
        raise Exception("WeirdPlace")
    return multi_subtasks
m_Place = CM.Method("Place", pre_cond=m_Place_precond, multi_decomp=m_Place_multi_decomp, get_precond=o_get_precond)


## Tries to place the cube in the stack, after being communicated
"""
def m_Place_comm_precond(state, agent, cube_name):
    flag_in_context = state.holding[agent]==cube_name and state.agent_at[agent]["agent_at_table"] == "table"
    # Check if the agent can place in the stack, if so find and return corresponding PT, else drop the cube back on thetable
    if not flag_in_context:
        return False
    elif cube_can_be_placed(state, cube_name):
        for l in state.solution:
            if (state.color_cubes[cube_name]["color"] in state.solution[l]["colors"] 
                and target_supports_ok(state, l) 
                and target_free(state, l)):
                return True
    return False

def m_Place_comm_multi_decomp(state, agent, cube_name):
    multi_subtasks = []

    # Check if the agent can place in the stack, if so find and return corresponding PT, else drop the cube back on thetable
    if cube_can_be_placed(state, cube_name):
        for l in state.solution:
            if (state.color_cubes[cube_name]["color"] in state.solution[l]["colors"] 
                and target_supports_ok(state, l) 
                and target_free(state, l)):
                multi_subtasks_loc = []
                
                if inspect_target_supports(state, l) != []:
                    for cube in inspect_target_supports(state, l):
                        multi_subtasks_loc.append(("Communicate", cube))
                    multi_subtasks_loc.append(("place", l, cube_name))
                    multi_subtasks_loc.append(("inspect_cube", cube_name))
                    multi_subtasks.append(multi_subtasks_loc)

                elif inspect_target_supports(state, l) == []:
                    for cube in inspect_target_supports(state, l):
                        multi_subtasks_loc.append(("Communicate", cube))
                    multi_subtasks_loc.append(("place", l, cube_name))
                    multi_subtasks_loc.append(("inspect_cube", cube_name))
                    multi_subtasks.append(multi_subtasks_loc)
                    # multi_subtasks.append([ ("place", l, cube_name), ("inspect_cube", cube_name) ])
    else:
        multi_subtasks.append([ ("Drop", cube_name) ])

    # if multi_subtasks==[]:
    #     raise Exception("WeirdPlace")
    return multi_subtasks
m_Place_after_comm = CM.Method("Place", pre_cond=m_Place_comm_precond, multi_decomp=m_Place_comm_multi_decomp)
"""

## Place from far##
# Tries to place the cube in the stack at the right place
def m_Place_far_precond(state, agent, cube_name):
    return (state.holding[agent] == cube_name 
            and state.agent_at[agent]["agent_at_table"] != "table")

def m_Place_far_multi_decomp(state, agent, cube_name):
    multi_subtasks = []

    # Check if the agent can place in the stack, if so find and return corresponding PTs/ATs
    if state.agent_in_context[agent]["table_context"] == "table":
        multi_subtasks.append([("move_to_table", state.agent_at[agent]["agent_at_table"], "table"), ("Place", cube_name)])
    else:
        multi_subtasks.append([ ("change_table_context", state.agent_at[agent]["agent_at_table"], "table"), 
                               ("move_to_table", state.agent_at[agent]["agent_at_table"], "table"), ("Place", cube_name)])

    return multi_subtasks
m_Place_far = CM.Method("Place", pre_cond=m_Place_far_precond, multi_decomp=m_Place_far_multi_decomp)


## Drop ##
# Tries to drop the cube in the center, otherwise on its own side
# For now always drop in the center
def m_Drop_multi_decomp(state, agent, cube_name):
    multi_subtasks = []

    multi_subtasks.append([ ("drop", cube_name, "C") ])

    return multi_subtasks
m_Drop = CM.Method("Drop", multi_decomp=m_Drop_multi_decomp)

common_methods = [m_Stack, m_Place, m_Unstack, m_Drop, m_Communicate]
robot_methods = common_methods + []
# human_methods = common_methods + [m_Communicate, m_Place_after_comm, m_Place_far, m_Stack_far, m_Pick_far]
human_methods = common_methods + [m_Place_far, m_Stack_far, m_Pick_far]

######################################################
###################### Triggers ######################
######################################################

common_triggers = []
robot_triggers = common_triggers + []
human_triggers = common_triggers + []


######################################################
###################### Helpers #######################
######################################################

def goal_reached(state):
    # If agents are not holding a cube
    if state.holding["H"]!=None or state.holding["R"]!=None:
        return False
    
    # And if each location has the correct color placed
    for l in state.locations:
        if not (state.locations[l] != None and state.color_cubes[state.locations[l]]["color"] in state.solution[l]["colors"]):
            return False
    return True    

def inspect_target_supports(state, loc):
    on_locs = state.solution[loc]["on"]
    if on_locs[0]=="table":
        return []
    else:
        cubes_to_inspect = []
        for on_loc in on_locs:
            if state.inspected_cube_to_place[ state.locations[on_loc] ]["inspected"] == False:
                cubes_to_inspect.append(state.locations[on_loc])
        return cubes_to_inspect
    
def target_supports_ok(state, loc):
    on_locs = state.solution[loc]["on"]
    if on_locs[0]=="table":
        return True
    else:
        for on_loc in on_locs:
            if state.locations[on_loc]==None:
                return False
        return True

def target_free(state, loc):
    return state.locations[loc]==None

def can_be_placed(state, color):
    for l in state.solution:
        if color in state.solution[l]["colors"] and target_supports_ok(state, l) and target_free(state, l):
            return True
    return False

def cube_side_reachable_by(state, cube, agent):
    ons = state.color_cubes[cube]["on"]

    if ons == []: ## it means that cube is being held or is already placed
        return False
    
    while not ons[0] in ["R", "C", "H"]:
        ons = state.color_cubes[ons[0]]["on"] 
    
    if is_robot(agent):
        return ons[0] in ["R", "C"]
    else:
        return ons[0] in ["H", "C"]
    
def cube_reachable_by(state, cube, agent):
    # if cube is in a side reachable by the agent or on the table
    # and if cube has no cubes on top of it
    # verify that if the agent is in the right context
    agent_in_right_position = (state.cube_at_table[cube]["at_table"] == state.agent_at[agent]["agent_at_table"])
    return (agent_in_right_position 
            and cube_side_reachable_by(state, cube, agent) 
            and state.color_cubes[cube]["below"]==None)

def cube_can_be_placed(state, cube):
    # hard coded
    # if not state.agent_at["H"]["agent_at_table"] == "table":
    #     return False    
    for l in state.solution:
        if state.color_cubes[cube]["color"] in state.solution[l]["colors"] and target_supports_ok(state, l) and target_free(state, l):
            return True
    return False

def is_robot(agent):
    return agent=="R"

######################################################
################## Goal Condition ####################
######################################################

def goal_condition(state):
    return goal_reached(state)


######################################################
######################## MAIN ########################
######################################################

def complete_color_cubes_info(state):
    for cube_name in state.color_cubes:
        state.color_cubes[cube_name]["color"] = cube_name[0]
        state.color_cubes[cube_name]["below"] = None

        # if there exists a block that is on another block and it is not available at either side i.e. R C H
        # then its "below" property captures which block is on top of it.
        if state.color_cubes[cube_name]["on"] != [] and state.color_cubes[cube_name]["on"][0] not in ['R', 'C', 'H']:
            state.color_cubes[state.color_cubes[cube_name]["on"][0]]["below"] = cube_name


def initDomain():
    # Set domain name
    domain_name = os.path.basename(__file__)[:-3] # filename minus ".py"
    CM.set_domain_name(domain_name)

    # Dynamic properties
    # name('color' + 'id) : {on:[cubes | side], color:c, below:None|cube}
    # color and below computed automatically
    # initial_state.create_dyn_fluent("color_cubes", { 
    #     "b1" : {"on":["R"]},
    #     "o1" : {"on":["b1"]},
    #     "g1" : {"on":["o1"]},
    #     "y1" : {"on":["R"]},
    #     "r1" : {"on":["R"]},
        
    #     "w1" : {"on":["C"]},
    #     "y2" : {"on":["C"]},
        
    #     "b2" : {"on":["H"]},
    #     "p1" : {"on":["H"]},
    # })


    # Initial state
    initial_state = CM.State("init")

    # Static properties
    initial_state.create_static_fluent("self_name", "None")
    initial_state.create_static_fluent("solution", {
        "l1" : {"colors":["r"], "on":["table"]},
        "l2" : {"colors":["y"], "on":["l1"]},
        # "l3" : {"colors":["p"], "on":["l1", "l2"]},
        # "l4" : {"colors":["b"], "on":["l3"]},
        # "l4": {"colors":["w"], "on":["l3"]},
    })

    # shashank - refined initial state
    initial_state.create_dyn_fluent("color_cubes", { 
        # "b1" : {"on":["R"]},
        # "o1" : {"on":["b1"]},
        # "g1" : {"on":["o1"]},
        
        # "y1" : {"on":["R"]},
        "r1" : {"on":["R"]},
        
        # "w1" : {"on":["C"]},
        "y2" : {"on":["H"]},
        
        # "b2" : {"on":["H"]},
        "p1" : {"on":["H"]}
    })

    initial_state.create_dyn_fluent("cube_at_table", {         
        "y1" : {"at_table": "table"},
        "r1" : {"at_table": "table"},
        
        "w1" : {"at_table": "table"},
        "y2" : {"at_table": "table_1"},

        "p1" : {"at_table": "table"}
    })

    initial_state.create_dyn_fluent("agent_in_context", {  
        # an agent can be in the context of table_1, the main table == Depicts facing the table        
        "H" : {"table_context": "table"},
        "R" : {"table_context": "table"}
    })

    initial_state.create_dyn_fluent("agent_at", {   
        # an agent can be situated at the main table or at table_1  
        "H" : {"agent_at_table": "table"},
        "R" : {"agent_at_table": "table"}
    })

    initial_state.create_dyn_fluent("inspected_cube_to_place", {   
        "y1" : {"inspected": False},
        "r1" : {"inspected": False},
        "w1" : {"inspected": False},
        "y2" : {"inspected": False},
        "p1" : {"inspected": False}
    })    

    # This way is for specifying the observability class 
    # For example: here the first element reports that the property [inspected_cube_to_place(cube, inspected)] is not observable.
    # This is true for any cube and its instected status.
    initial_state.create_static_fluent("observability_class", {   
        "inspected_cube_to_place" : {"observable": False}
        # ... other properties
    })


    # We will define context to manage an observable state property from the environment 
    # they will be a special form of operators
    # defined above 
    
    complete_color_cubes_info(initial_state)
    initial_state.create_dyn_fluent("locations", {})
    for l in initial_state.solution:
        # in the beginning there is nothing on those solution locations
        initial_state.locations[l] = None

    initial_state.create_dyn_fluent("holding", {"R":None, "H":None})
    CM.set_state(initial_state)

    # Robot init #
    CM.declare_operators("R", robot_ops)
    CM.declare_methods("R", robot_methods)
    CM.add_tasks("R", [("Stack",)])

    # Human init #
    CM.declare_operators("H", human_ops)
    CM.declare_methods("H", human_methods)
    CM.add_tasks("H", [("Stack",)])

    CM.set_starting_agent("H")

def main(tt_explore):
    sys.setrecursionlimit(100000)
    initDomain()
    # pr = cProfile.Profile()
    # pr.enable()

    s_t = time.time()
    sol = ConM.explore(tt_explore)
    print("time to explore: %.2fs" %(time.time()-s_t))
    print(f"Number of leaves: {len(sol.get_final_leaves(tt_explore))}")
    print(f"Nb states = {sol.get_nb_states()}")
    
    # pr.disable()
    # stats = pstats.Stats(pr).sort_stats("tottime")
    # stats.dump_stats(filename="profiling.prof")
    return sol

if __name__ == "__main__":

    #shashank
    tt_explore = True

    if len(sys.argv)>1 and sys.argv[1]=="tt":
        tt_explore = True
    
    sol = main(tt_explore)

    solution_checker.check_solution(sol, goal_condition)

    ConM.simplify_solution(sol)

    ConM.dumping_solution(sol, tt_explore)