import dill
import graphviz
import sys
import concurrent.futures
import time

import matplotlib.pyplot as plt


import CommonModule as CM
import ConcurrentModule as ConM


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

    filename = "dom_n_sol.p"
    if len(sys.argv)>1:
        filename = sys.argv[1]

    return load(filename)

def dump(filename, begin_step):
    print(f"Dumping ranked solutions '{filename}'...  ", end="", flush=True)
    s_t = time.time()

    dill.dump((g_domain_name, begin_step), open(CM.path + filename, "wb"))

    print("Dumped! - %.2fs" %(time.time()-s_t))

def dump_solution(begin_step):
    filename = "dom_n_sol_with_choices.p"
    if len(sys.argv)>1:
        filename = sys.argv[1][:-2] + "_with_choices.p"

    dump(filename, begin_step)



def check_if_branch_best_human_choice(leaf_step: ConM.Step):
    pair = leaf_step.get_pairs()[0]
    while not pair.previous.is_begin():
        if not CM.Action.are_similar(pair.get_in_step().parent.best_human_pair.human_action, pair.previous.human_action):
            return False
        pair = pair.previous
    return True

def find_r_rank_of_id(steps, id):
    for s in steps:
        if s.id == id:
            return s.get_f_leaf().branch_rank_r

def convert_rank_to_score(rank, nb):
    return -1/(nb-1) * rank + nb/(nb-1)

def sort_and_update_r(begin_step, final_leaves, r_criteria):
    r_ranked_leaves = ConM.sorting_branches(final_leaves, r_criteria, is_robot=True)
    ConM.update_robot_choices(begin_step)
    return r_ranked_leaves

def sort_and_update_h(begin_step, final_leaves, h_criteria):
    h_ranked_leaves = ConM.sorting_branches(final_leaves, h_criteria, is_robot=False)
    ConM.update_human_choices(begin_step)
    return h_ranked_leaves

def main():
    global g_domain_name
    sys.setrecursionlimit(100000)

    g_domain_name, begin_step = load_solution()

    # human_min_work    #
    # human_free_early  #
    # task_end_early    #
    r_esti = "human_min_work"
    r_criteria = ConM.get_exec_prefs()[r_esti]


    print(f"Updating policy '{r_esti}' ... ", end="", flush=True)
    s_t = time.time()

    e = concurrent.futures.ThreadPoolExecutor(max_workers=3)
    final_leaves = begin_step.get_final_leaves()
    r_job = e.submit(sort_and_update_r, begin_step, final_leaves, r_criteria)
    # h_job = e.submit(sort_and_update_h, begin_step, final_leaves, h_criteria)

    r_ranked_leaves = r_job.result()
    # h_ranked_leaves = h_job.result()

    e.shutdown(wait=True)


    print("Done! - %.2fs" %(time.time()-s_t))
    print(f"Number of leaves: {len(begin_step.get_final_leaves())}")
    print(f"Nb states = {begin_step.get_nb_states()}")


    # f = open("ranks.txt", "w")
    # f.write("R sorting\n")
    # f.write(ConM.get_str_ranked_branches(r_ranked_leaves, robot=True))
    # # f.write("H sorting\n")
    # # f.write(ConM.get_str_ranked_branches(h_ranked_leaves, robot=False))
    # f.close()

    dump_solution(begin_step)

    exit()

    xdata = []
    ydata = []
    for l in h_ranked_leaves:
        xdata.append( convert_rank_to_score(l.get_f_leaf().branch_rank_h, len(h_ranked_leaves)) )
        ydata.append( convert_rank_to_score(find_r_rank_of_id(h_ranked_leaves, l.id),len(h_ranked_leaves)) )

    
    fig, ax = plt.subplots()

    # plt.figure(figsize=(2,2))
    # plt.xlim(0,1.0)
    # plt.ylim(0,1.0)

    ax.plot(xdata, ydata, 'b+')
    ax.set_xlim(0,1.0)
    ax.set_ylim(0,1.0)
    ax.set_xlabel("H-Score")
    ax.set_ylabel("R-Score")

    ratio = 1.0
    x_left, x_right = ax.get_xlim()
    y_low, y_high = ax.get_ylim()
    ax.set_aspect(abs((x_right-x_left)/(y_low-y_high))*ratio)

    ticks = [0.0,0.5,1.0]
    labels = ["0.0", "0.5", "1.0"] 
    ax.set_xticks(ticks, labels=labels)
    ax.set_yticks(ticks, labels=labels)

    size = 2.5
    fig.set_size_inches(size,size)
    fig.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()