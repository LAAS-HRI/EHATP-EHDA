import dill
import graphviz
import sys
import time

import CommonModule as CM
import ConcurrentModule as ConM


import random
import string

def load(filename):

    print(f"Loading solution '{filename}' ... ", end="", flush=True)
    s_t = time.time()

    domain_name, init_step = dill.load(open(CM.path + filename, "rb"))

    print("Loaded! - %.2fs" %(time.time()-s_t))

    return domain_name, init_step


def load_solution():
    """
    Loads the previously produced solution.
    The domain name is retreived and returned and as well as the solution tree and the initial step.
    """

    # old file
    # filename = "dom_n_sol_with_choices.p"
    filename = "dom_n_sol_tt.p"
    if len(sys.argv)>1:
        filename = sys.argv[1]

    return load(filename)


def action_gui_str(action: CM.Action, show_id=False):
    task_name = action.name if action.name != "PASSIVE" else "PASSIVE"
    base_str = f"{task_name}{action.parameters}"

    id_str = ""
    if show_id:
        id_str = f"{action.id}-"

    return id_str + base_str

G_METRICS = False

def render_dot_new(init_step: ConM.Step, max_depth=None, ignored_step_ids=[], show_only={}, show_only_branch=None, pdf=False, show_optimal=False, with_next_step=False):
    global g_opti_branch_id
    format_file = "svg" if not pdf else "pdf"
    g = graphviz.Digraph('G', filename='render_dot.gv', format=format_file, 
        engine="dot",
        # engine="neato",
        graph_attr=dict(splines='true',
                        sep='5',
                        nslimit='2',
                        nslimit1='2',
                        overlap='scale'),
    )
    g.attr(compound='true')

    if show_only_branch!=None:
        max_depth=None
        ignored_step_ids=[]
        show_only={}

    # g.edge_attr["minlen"]="2"

    steps_to_render = [init_step]

    begin_node_name=""

    i_cluster=0
    while steps_to_render != []:
        s = steps_to_render.pop(0)

        if show_only_branch!=None and not show_only_branch in [leaf.id for leaf in s.get_final_leaves()]:
            continue
        if max_depth!=None and s.depth > max_depth:
            continue
        if s.depth in show_only and show_only[s.depth]!=s.id:
            continue
        if s.id in ignored_step_ids:
            continue

        if s.is_root:
            begin_node_name = s.human_options[0].action_pairs[0].get_short_str()
            g.node(begin_node_name, shape='circle', style="filled", color="black", label="", width="0.2", fixedsize="true")
        elif s.is_final():
            metrics_str = ""
            if s.parent.best_robot_pair!=None:
                for m in s.human_options[0].action_pairs[0].branch_metrics.values():
                    metrics_str +=  f"-" if not metrics_str=="" else "\n"
                    metrics_str += format(m, ".3g")
                metrics_str += f"\n#{s.get_f_leaf().branch_rank_r}"
            name = "f_"+s.human_options[0].action_pairs[0].get_short_str()
            g.node(name, shape='doublecircle', style="filled", color="black", label="", xlabel="("+str(s.id)+")"+metrics_str, width="0.2", fixedsize="true")
            if s.from_pair!=None:
                g.edge(str(s.from_pair.get_short_str()), name)
        else:
            name_step_cluster = f"cluster_{i_cluster}"
            one_node=""
            with g.subgraph(name=name_step_cluster) as cs:
                i_cluster += 1
                cs.attr(style='solid', bgcolor="#f3f3f3", label=f"{s.depth}-Step{s.get_str(with_bold=False)}")
                for ho in s.human_options:
                    with cs.subgraph(name=f"cluster_{i_cluster}") as c:
                        i_cluster += 1
                        h_label = action_gui_str(ho.human_action)
                        if s.best_robot_pair!=None and CM.Action.are_similar(ho.human_action, s.best_robot_pair.human_action):
                            # h_label= '< <B>#' + h_label + '#</B> >'
                            h_label= '#' + h_label + '#'
                        c.attr(label=h_label, style='rounded', color="#D6B656", bgcolor="#FFE6CC")
                        
                        for p in ho.action_pairs:
                            node_name = p.get_short_str()

                            # Style
                            if p.robot_action.name=="SKIP" or ConM.check_list(s.CRA, lambda x: CM.Action.are_similar(x, p.robot_action)):
                                style="filled,bold,rounded"
                            elif p.robot_action.is_passive():
                                style = "filled,solid,rounded"
                            else:
                                style = "filled,solid,rounded"

                            # Shape
                            shape = "ellipse"
                            if p.robot_action.is_passive():
                                shape = "box"

                            r_label=action_gui_str(p.robot_action)
                            
                            if p.in_human_option.best_robot_pair!=None and p==p.in_human_option.best_robot_pair:
                                # r_label = '''< <table border="0"><tr><td align="text">By default, td text is center-aligned<br align="right" /></td></tr></table> >'''
                                # r_label= '< <B>#' + r_label + '#</B> >'
                                r_label= '#' + r_label + '#'
                            if with_next_step and len(p.next):
                                r_label += f"\n({p.next[0].get_in_step().id})"

                            # r_label +=  "\n copresence: " + str(p.copresence) 
                            c.node(node_name, label=r_label, shape=shape, style=style, color="#6C8EBF", fillcolor="#DAE8FC")

                            # c.node(node_name+"ss", label=r_label+"xx", shape=shape, style=style, color="#6C8EBF", fillcolor="#DAE8FC")

                            if one_node=="":
                                one_node=node_name

            if s.from_pair!=None:
                if s.from_pair.get_in_step().is_root:
                    g.edge(str(s.from_pair.get_short_str()), one_node, lhead=name_step_cluster, minlen="2")
                else:
                    g.edge(str(s.from_pair.get_short_str()), one_node, lhead=name_step_cluster)

        if show_optimal:
            for child in s.children:
                if s.is_root or child.from_pair == s.best_robot_pair:
                    steps_to_render += [child]
            if len(s.children)==0:
                g_opti_branch_id = s.id
        else:
            steps_to_render += [child for child in s.children]

    g.view()

def generate_random_characters():
    return ''.join(random.choices(string.ascii_letters, k=3))


def render_dot_new_agent(init_step: ConM.Step, max_depth=None, ignored_step_ids=[], show_only={}, show_only_branch=None, pdf=False, show_optimal=False, with_next_step=False):
    global g_opti_branch_id
    format_file = "svg" if not pdf else "pdf"
    g = graphviz.Digraph('G', filename='render_dot.gv', format=format_file, 
        engine="dot",
        # engine="neato",
        graph_attr=dict(splines='true',
                        sep='5',
                        nslimit='2',
                        nslimit1='2',
                        overlap='scale'),
    )
    g.attr(compound='true')

    if show_only_branch!=None:
        max_depth=None
        ignored_step_ids=[]
        show_only={}

    # g.edge_attr["minlen"]="2"

    steps_to_render = [init_step]

    begin_node_name=""

    i_cluster=0
    while steps_to_render != []:
        # 
        s = steps_to_render.pop(0)

        if show_only_branch!=None and not show_only_branch in [leaf.id for leaf in s.get_final_leaves()]:
            continue
        if max_depth != None and s.depth > max_depth:
            continue
        if s.depth in show_only and show_only[s.depth]!=s.id:
            continue
        if s.id in ignored_step_ids:
            continue

        if s.is_root:
            begin_node_name = s.human_options[0].action_pairs[0].get_short_str()
            g.node(begin_node_name, shape='circle', style="filled", color="black", label="", width="0.2", fixedsize="true")
            
            ## Define what to show in the node ##   
            box_type_all_worlds = ""
            count = 0
            str_tot_w = "Total number of worlds:" + str(len(s.children[0].from_pair.possible_worlds_for_h) + 1) + "\n"

            str_tot_w += "\n(Only relevant) details for the INITIAL (epistemic) state:\n"  
            for wrld in s.children[0].from_pair.possible_worlds_for_h:
                count += 1
                box_type_all_worlds = return_states_imp_features(wrld.state, box_type_all_worlds, count)                            


            ### Below I have listed the static facts, just for the initial state ###
            wrld = s.children[0].from_pair.end_agents.state
            count += 1
            each_world_box_type = "\n(Designated) "   
            each_world_box_type = return_states_imp_features(wrld, each_world_box_type, count)                       
            box_type_all_worlds += each_world_box_type         

            box_type_all_worlds += "\n[[Some static facts in the initial state are specified as follows]]\n"
            cube_belongs_to = ""
            wrld = s.children[0].from_pair.end_agents
            for cube in wrld.state.color_cubes:
                cube_belongs_to += "cube_belongs_to_table(" + str(cube) + ") = " + str(wrld.state.cube_belongs_table[cube]["at_table"]) + ",\t"
            if not cube_belongs_to == "":
                box_type_all_worlds += cube_belongs_to

            each_world_box_type = ""                            
            for box in wrld.state.box_at_table:
                each_world_box_type += "box_type(" + str(box) + ") = " + str(wrld.state.box_transparent_type[box]["type"]) + ",\t"
            
            if not each_world_box_type == "":
                box_type_all_worlds += each_world_box_type
            
            box_on_table = ""                            
            for box in wrld.state.box_at_table:
                box_on_table += "box_on_table(" + str(box) + ") = " + str(wrld.state.box_on_table[box]["on_table"][0]) + ",\t"
            
            if not box_on_table == "":
                box_type_all_worlds += box_on_table

            # goal state
            box_type_all_worlds += "\n\n[[Each goal state must satisfy the following goal conditions]]"
            box_type_all_worlds += "\n" + "GOAL: all cubes belonging to the same table initially, should be contained in one box eventually!!" + "\n"
            
            box_type_all_worlds += "\n" +"Who starts first? : " + "HUMAN" 

            # with g.subgraph(name=f"cluster_{i_cluster}") as c2:
            g.attr(shape="doublecircle", style='solid', label=f"")
            g.node(begin_node_name +"_1", shape='ellipse', label= str_tot_w + "\n" + box_type_all_worlds)
            # if "SIGNAL" in h_label or "communicate" in h_label or "take_out" in r_label: 
            g.edge(begin_node_name, begin_node_name + "_1", label=f'<<b><font color="blue">A rough description of Init State and GOAL</font></b>>', headport='n', tailport='s')

            # g.view()

        elif s.is_final():
            metrics_str = ""
            if s.parent.best_robot_pair!=None:
                for m in s.human_options[0].action_pairs[0].branch_metrics.values():
                    metrics_str +=  f"-" if not metrics_str=="" else "\n"
                    metrics_str += format(m, ".3g")
                metrics_str += f"\n#{s.get_f_leaf().branch_rank_r}"
            name = "f_"+s.human_options[0].action_pairs[0].get_short_str()
            g.node(name, shape='doublecircle', style="filled", color="black", label="", xlabel="("+str(s.id)+")"+metrics_str, width="0.2", fixedsize="true")
            if s.from_pair!=None:
                g.edge(str(s.from_pair.get_short_str()), name) 
        else:
            name_step_cluster = f"cluster_{i_cluster}"

            ### in case of confusion, just play with this code block ###
            # with g.subgraph(name=name_step_cluster) as cs:
            #     i_cluster += 1
            #     cs.attr(label="h_label_1", style='rounded', color="#D6B656", bgcolor="#FFE6CC")
            #     cs.node('Node1', label="SHYAM_1", shape="box", style="solid", color="#6C8EBF", fillcolor="#DAE8FC")
            #     cs.node('Node2', label="RAM_1", shape="box", style="solid", color="#6C8EBF", fillcolor="#DAE8FC")
            # for i in range(2):
            #     with g.subgraph(name=name_step_cluster+str(i)) as cs1:
            #         print (i)
            #         cs1.attr(label="h_label", style='rounded', color="red", bgcolor="#FFE6CC")
            #         cs1.node('Node11'+str(i), label="SHYAM"+str(i), shape="box", style="solid", color="#6C8EBF", fillcolor="#DAE8FC")
            #         cs1.node('Node21'+str(i), label="RAM"+str(i), shape="box", style="solid", color="#6C8EBF", fillcolor="#DAE8FC")
            ### in case of confusion, just play with this code block ###
                           
            one_node=""
            with g.subgraph(name=name_step_cluster) as cs:         
                # i_cluster += 1
                copresence = f'<<b><font color="blue">CoPresence: <font color="red">{str(s.from_pair.copresence).upper()}</font></font></b>>'
                cs.attr(rankdir='TB', style='solid', bgcolor="#f3f3f3", color="black", label=copresence)     
                if s.from_pair.copresence:
                    for ho in s.human_options:
                        i_cluster += 1
                        with cs.subgraph(name=f"cluster_{i_cluster}") as cs_local:                            
                            h_label = action_gui_str(ho.human_action)
                            if s.best_robot_pair!=None and CM.Action.are_similar(ho.human_action, s.best_robot_pair.human_action):
                                # h_label= '< <B>#' + h_label + '#</B> >'
                                h_label= '#' + h_label + '#'
                            
                            # if "WAIT" in h_label and not("SIGNAL" in h_label):
                            # cs_local.attr(label="", style='rounded', color="#D6B656", bgcolor="#FFE6CC", labelloc="c", labeljust="c", rankdir='TB')
                            # else:
                            cs_local.attr(label="[H]: " + h_label, style='rounded', color="#D6B656", bgcolor="#FFE6CC", labelloc="c", labeljust="c", rankdir='TB')

                            for p in ho.action_pairs:                            
                                node_name = p.get_short_str()    

                                # Style
                                if p.robot_action.name=="SKIP" or ConM.check_list(s.CRA, lambda x: CM.Action.are_similar(x, p.robot_action)):
                                    style = "filled,bold,rounded"
                                elif p.robot_action.is_passive():
                                    style = "filled,solid,rounded"
                                else:
                                    style = "filled,solid,rounded"

                                # Shape
                                shape = "ellipse"
                                if p.robot_action.is_passive():
                                    # shape = "box"
                                    shape = "ellipse"

                                r_label=action_gui_str(p.robot_action)
                                
                                if p.in_human_option.best_robot_pair!=None and p==p.in_human_option.best_robot_pair:
                                    # r_label = '''< <table border="0"><tr><td align="text">By default, td text is center-aligned<br align="right" /></td></tr></table> >'''
                                    # r_label= '< <B>#' + r_label + '#</B> >'
                                    r_label= '#' + r_label + '#'
                                if with_next_step and len(p.next):
                                    r_label += f"\n({p.next[0].get_in_step().id})"

                                # r_label +=  "\n copresence: " + str(p.copresence) 
                                # if "WAIT" in r_label:    
                                #     c.node(node_name, label="", shape=shape, style="invis", color="#6C8EBF", fillcolor="#DAE8FC", labelloc="c", labeljust="c")
                                # else:
                                #     c.node(node_name, label="[R]: " + r_label, shape=shape, style=style, color="#6C8EBF", fillcolor="#DAE8FC", labelloc="c", labeljust="c")                               
                                
                                # why to have a node for robot is it does not extend
                                shall_the_node_appear = False
                                for ch in s.children:
                                    if ch.from_pair.get_short_str() == node_name:
                                        shall_the_node_appear = True
                                        break
                                
                                if not shall_the_node_appear:
                                    continue

                                cs_local.node(node_name, label="[R]: " + r_label, shape=shape, style=style, color="#6C8EBF", fillcolor="#DAE8FC", labelloc="c", labeljust="c", rankdir='TB')                               
                
                                # if one_node=="":
                                one_node=node_name    

                                action_pair_tokeep = False
                                child_details = None
                                for ch in s.children:
                                    if p.get_short_str() == ch.from_pair.get_short_str():
                                        action_pair_tokeep = True
                                        child_details = ch
                                
                                if not action_pair_tokeep:
                                    continue

                                num_worlds = 0
                                if action_pair_tokeep:
                                    num_worlds = len(child_details.from_pair.possible_worlds_for_h) + 1

                                ## Define what to show in the node ##   
                                box_type_all_worlds = ""
                                count = 0
                                str_tot_w = "Total number of worlds:" + str(num_worlds) + "\n"
                                # str_tot_w = f'<<b><font color="blue">Total number of worlds:<font color="red">{str(num_worlds)}</font></font></b>>'

                                if "SIGNAL" in h_label or "communicate" in h_label or "take_out" in r_label:                                
                                    # str_tot_w += "\n\nDetails after SA and INF \n"  
                                    for wrld in child_details.from_pair.possible_worlds_for_h:
                                        count += 1
                                        box_type_all_worlds = return_states_imp_features(wrld.state, box_type_all_worlds, count)                            

                                    wrld = child_details.from_pair.end_agents.state
                                    count += 1
                                    each_world_box_type = "\n(Designated) "   
                                    each_world_box_type = return_states_imp_features(wrld, each_world_box_type, count)                       
                                    box_type_all_worlds += each_world_box_type + "\n"        

                                with cs.subgraph(name=f"cluster_{i_cluster}") as c2:
                                    c2.attr(shape=shape, style='solid', bgcolor="lightyellow", label=f"")
                                    c2.node(node_name + "_1", shape = "box", label= str_tot_w + "\n" + box_type_all_worlds)
                                    if "SIGNAL" in h_label or "communicate" in h_label or "take_out" in r_label: 
                                        label=f'<<b><font color="blue">Post SA and INF</font></b>>'
                                        g.edge(one_node, node_name + "_1", lhead=name_step_cluster, label=label, len='0.5') 
                                # g.view()
                elif not s.from_pair.copresence and len(s.children)==1:
                    with g.subgraph(name=name_step_cluster) as cs1:   
                        # cs1.attr(style='solid', bgcolor="#f3f3f3", label=f"[Copresence]: [{str(s.from_pair.copresence).upper()}]")
                    
                        parent_s = s
                        children_s = parent_s.children

                        action_pair_1 = None
                        for ho in s.human_options:
                            for ap in ho.action_pairs:
                                for ch in children_s:
                                    if ap.get_short_str() == ch.from_pair.get_short_str():
                                        action_pair_1 = ap 
                        
                        action_pair_2 = None
                        for ho in children_s[0].human_options:
                            for ap in ho.action_pairs:
                                for ch in children_s[0].children:
                                    if ap.get_short_str() == ch.from_pair.get_short_str():
                                        action_pair_2 = ap

                        for child in children_s:
                            for ho in child.human_options:
                                with cs1.subgraph(name=f"cluster_{i_cluster}") as c1:
                                    i_cluster += 1
                                    h_label = action_gui_str(ho.human_action)                                
                                    node_name_h = action_pair_1.get_short_str()
                                    # c1.attr(label= "[H]: " + h_label, style='rounded', color="#D6B656", bgcolor="#FFE6CC", labelloc="c", labeljust="c")                                
                                    c1.node(node_name_h, label = "[H]: " + h_label, shape="box", style=style, color="#6C8EBF", fillcolor="#DAE8FC")
                                    node_name = action_pair_2.get_short_str()
                                    # node_name = ho.
                                    r_label=action_gui_str(action_pair_1.robot_action)
                                    style = "filled,solid,rounded"
                                    c1.node(node_name, label = "[R]: " + r_label, shape="ellipse", style=style, color="#6C8EBF", fillcolor="#DAE8FC")
                                    child.from_pair = action_pair_1
                                    if one_node=="":
                                        one_node=node_name
                        
                        i_cluster += 1 

                        # Define what to show in the node#   
                        box_type_all_worlds = ""
                        count = 0

                        str_tot_w = "Total number of worlds: " + str(len(s.children[0].children[0].from_pair.possible_worlds_for_h)+1) + "\n"
                        num_worlds = len(s.children[0].children[0].from_pair.possible_worlds_for_h) + 1
                        # str_tot_w = f'<<b><font color="blue">Total number of worlds:<font color="red">{str(len(s.children[0].children[0].from_pair.possible_worlds_for_h) + 1)}</font></font></b>>'

                        for wrld in s.children[0].children[0].from_pair.possible_worlds_for_h:
                            count += 1
                            box_type_all_worlds = return_states_imp_features(wrld.state, box_type_all_worlds, count)                            

                        wrld = s.children[0].children[0].from_pair.end_agents.state
                        count += 1
                        each_world_box_type = "\n(Designated) "   
                        each_world_box_type = return_states_imp_features(wrld, each_world_box_type, count)                       
                        
                        box_type_all_worlds += each_world_box_type + "\n"                        

                        with cs1.subgraph(name=f"cluster_{i_cluster}") as c2:
                            c2.attr(style='solid', bgcolor="lightyellow", label=f"")
                            c2.node(node_name + "_1", label= str_tot_w + "\n" + box_type_all_worlds)

                            g.edge(one_node, node_name + "_1", lhead=name_step_cluster, label=f'<<b><font color="blue">Post SA and INF</font></b>>', headport='n', tailport='s')    
                        # g.view() 
            if s.from_pair!=None:
                if s.from_pair.get_in_step().is_root:
                    g.edge(str(s.from_pair.get_short_str()) + "_1", one_node, minlen="2")
                else:
                    g.edge(str(s.from_pair.get_short_str()) + "_1", one_node) 
            # g.view()       
        if show_optimal:
            for child in s.children:
                if s.is_root or child.from_pair == s.best_robot_pair:
                    steps_to_render += [child]
            if len(s.children)==0:
                g_opti_branch_id = s.id
        else:
            if s.depth == 0:
                steps_to_render += [child for child in s.children]
            elif s.from_pair.copresence and s.depth > 0:
                steps_to_render += [child for child in s.children]
            elif not s.from_pair.copresence:
                steps_to_render += [child for child in s.children[0].children]
            # if s.depth == 0:
            #     steps_to_render += [child for child in s.children]
            # elif(s.from_pair.node_type == "AND"):
            #     steps_to_render += [child for child in s.children]
            # elif(s.from_pair.node_type == "OR"):
            #     special_child = next((child for child in s.children if child.from_pair.node_done == "DONE"), None)
            #     steps_to_render += [special_child]
            # g.view() 
    g.view()
    

def return_states_imp_features(state, worlds_imp_features, count):
    each_world_box_type = "World - " + str(count) + " : "                            
    # for box in state.box_at_table:
    #     each_world_box_type += "box_type(" + str(box) + ") = " + str(state.box_transparent_type[box]["type"]) + ",\t"
    worlds_imp_features += each_world_box_type 

    cube_held = ""
    for cube in state.color_cubes:
        if cube == state.holding["R"]:
            cube_held += "holding(R) = " + str(state.holding["R"]) + ",\t"
        elif cube == state.holding["H"]:
            cube_held += "holding(H) = " + str(state.holding["H"]) + ",\t"
    if not cube_held == "":
        worlds_imp_features += cube_held 

    agent_at = ""
    agent_at += "agent_at(R) = " + str(state.agent_at["R"]["agent_at_table"]) + ",\t"
    agent_at += "agent_at(H) = " + str(state.agent_at["H"]["agent_at_table"]) + ",\t"
    if not agent_at == "":
        worlds_imp_features += agent_at

    facing_table = ""
    facing_table += "facing_table(R) = " + str(state.agent_in_context["R"]["table_context"]) + ",\t"
    facing_table += "facing_table(H) = " + str(state.agent_in_context["H"]["table_context"]) + ",\t"
    if not facing_table == "":
        worlds_imp_features += facing_table

    cube_at = ""
    for cube in state.color_cubes:
        if state.cube_at_table[cube]["at_table"] != None:
            cube_at += "cube-at-table(" + str(cube) + ") = " + str(state.cube_at_table[cube]["at_table"]) + ",\t"
    if not cube_at == "":
        worlds_imp_features += cube_at

    who_has_access_cubes_initially = ""
    for cube in state.color_cubes:
        if state.color_cubes[cube]["on"] != []:
            who_has_access_cubes_initially += "who-can-access(" + str(cube) + ") = " + str(state.color_cubes[cube]["on"]) + ",\t"
    if not who_has_access_cubes_initially == "":
        worlds_imp_features += who_has_access_cubes_initially

    box_contains = ""
    for box in state.box_at_table:
        for cube in state.box_containing[box]["contains"]:
            box_contains += "cube-contains-in-box(" + str(cube) +") = " + str(box) + ",\t"
    
    if not box_contains == "":
        worlds_imp_features += box_contains + "\n"
    else:
        worlds_imp_features += "\n"

    return worlds_imp_features



if __name__ == "__main__":
    # 
    domain_name, begin_step = load_solution()
    # 
    max_depth = None
    ignored_steps_ids = []
    show_only = {}
    g_opti_branch_id = -1
    while True:
        print(" ")
        print("0) Render")
        print("1) Set max depth")
        print("2) Set ignored steps")
        print("3) Set show only")
        print("4) Explore")
        print("5) Show only branch id")
        print("6) Reset")
        print("7) Set Criteria")
        print("8) Render pdf")
        print("9) Render optimal plan")
        print("Choice: ", end="")

        choice = input()

        # print("(enter H/R to extract agent's plan)")
        # agent = input()
        # agent = "H"

        if choice=="0":
            render_dot_new(begin_step, max_depth=max_depth, ignored_step_ids=ignored_steps_ids, show_only=show_only)
            # render_dot_new_agent(begin_step, max_depth=max_depth, ignored_step_ids=ignored_steps_ids, show_only=show_only)
        elif choice=="1":
            show_only_branch=None
            print("Current max depth: ", max_depth)
            print("Enter new max depth (d | r): ", end="")
            choice = input()
            if choice=="r":
                max_depth = None
            else:
                max_depth = int(choice)
            print(f"New max depth {max_depth}")

        elif choice=="2":
            show_only_branch=None
            print("Current ignored steps: ", ignored_steps_ids)
            print("Enter new ignored steps: ", end="")
            choice = input()
            if choice=="":
                ignored_steps_ids=[]
            else:
                choice = choice.replace(" ", "")
                choice = choice.split(",")
                ignored_steps_ids = [int(id) for id in choice]
            print(f"New ignored steps: {ignored_steps_ids}")

        elif choice=="3":
            show_only_branch=None
            print("Current show only: ", show_only)
            print("Enter new show only (depth, id | r): ", end="")
            choice = input()
            if choice=="":
                show_only={}
            else:
                choice = choice.replace(" ", "")
                choice = choice.split(",")
                depth = int(choice[0])
                id = choice[1]
                if id=="r":
                    show_only.pop(depth)
                else:
                    id = int(id)
                    show_only[depth] = id
            print(f"New show_only: {show_only}")

        elif choice=="4":
            show_only_branch=None
            explo_depth = 1
            explo_show_only = {}
            explo_show_only[explo_depth] = 1
            render_dot_new(begin_step, max_depth=explo_depth, show_only=explo_show_only, with_next_step=True)

            choice = None
            while choice!="q":
                print("Enter step to explore (id | s | r | q): ", end="")
                choice = input()

                if choice=="s":
                    max_depth = explo_depth
                    show_only = explo_show_only
                
                elif choice=="r":
                    explo_show_only.pop(explo_depth)
                    explo_depth -= 1
                    render_dot_new(begin_step, max_depth=explo_depth, show_only=explo_show_only, with_next_step=True)

                elif choice!="q":
                    explo_depth += 1
                    explo_show_only[explo_depth] = int(choice) 
                    render_dot_new(begin_step, max_depth=explo_depth, show_only=explo_show_only, with_next_step=True)

        elif choice=="5":
            print("Enter id branch: ", end="")
            choice = int(input())
            show_only_branch = choice
            render_dot_new(begin_step, show_only_branch=choice)

        elif choice=="6":
            show_only_branch=None
            max_depth = None
            ignored_steps_ids = []
            show_only = {}

        elif choice=="7":
            pass

        elif choice=="8":
            render_dot_new(begin_step, max_depth=max_depth, ignored_step_ids=ignored_steps_ids, show_only=show_only, show_only_branch=show_only_branch, pdf=True)

        elif choice=="9":
            render_dot_new(begin_step, show_optimal=True)
            show_only_branch = g_opti_branch_id






        