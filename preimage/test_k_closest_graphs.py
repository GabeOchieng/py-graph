#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Dec 16 11:53:54 2019

@author: ljia
"""
import numpy as np
import math
import networkx as nx
import matplotlib.pyplot as plt
import time
import random
from tqdm import tqdm
from itertools import combinations, islice
import multiprocessing
from multiprocessing import Pool
from functools import partial

#import os
import sys
sys.path.insert(0, "../")
from pygraph.utils.graphfiles import loadDataset, loadGXL
#from pygraph.utils.logger2file import *
from iam import iam_upgraded, iam_bash
from utils import compute_kernel, dis_gstar, kernel_distance_matrix
from fitDistance import fit_GED_to_kernel_distance
#from ged import ged_median


def median_on_k_closest_graphs(Gn, node_label, edge_label, gkernel, k, fit_method,
                               graph_dir='/media/ljia/DATA/research-repo/codes/Linlin/py-graph/datasets/monoterpenoides/', 
                               edit_costs=None, group_min=None, dataset='monoterpenoides',
                               cost='CONSTANT', parallel=True):
    dataset = dataset.lower()
    
#    # compute distances in kernel space.
#    dis_mat, _, _, _ = kernel_distance_matrix(Gn, node_label, edge_label, 
#                                              Kmatrix=None, gkernel=gkernel)
#    # ged.
#    gmfile = np.load('results/test_k_closest_graphs/ged_mat.fit_on_whole_dataset.with_medians.gm.npz')
#    ged_mat = gmfile['ged_mat']
#    dis_mat = ged_mat[0:len(Gn), 0:len(Gn)]
    
#    # choose k closest graphs
#    time0 = time.time()
#    sod_ks_min, group_min = get_closest_k_graphs(dis_mat, k, parallel)
#    time_spent = time.time() - time0
#    print('closest graphs:', sod_ks_min, group_min)
#    print('time spent:', time_spent)
#    group_min = (12, 13, 22, 29) # closest w.r.t path kernel
#    group_min = (77, 85, 160, 171) # closest w.r.t ged
#    group_min = (0,1,2,3,4,5,6,7,8,9,10,11) # closest w.r.t treelet kernel
    Gn_median = [Gn[g].copy() for g in group_min]


    # fit edit costs.    
    if fit_method == 'random': # random
        if cost == 'LETTER':
            edit_cost_constant = random.sample(range(1, 10), 3)
            edit_cost_constant = [item * 0.1 for item in edit_cost_constant]
        elif cost == 'LETTER2':
            random.seed(time.time())
            edit_cost_constant = random.sample(range(1, 10), 5)
#            edit_cost_constant = [item * 0.1 for item in edit_cost_constant]
        else:
            edit_cost_constant = random.sample(range(1, 10), 6)
        print('edit costs used:', edit_cost_constant)
    elif fit_method == 'expert': # expert
        edit_cost_constant = [3, 3, 1, 3, 3, 1]
    elif fit_method == 'k-graphs':
        itr_max = 6
        if cost == 'LETTER':
            init_costs = [0.9, 1.7, 0.75] 
        elif cost == 'LETTER2':
            init_costs = [0.675, 0.675, 0.75, 0.425, 0.425]
        else:
            init_costs = [3, 3, 1, 3, 3, 1] 
        algo_options = '--threads 1 --initial-solutions 40 --ratio-runs-from-initial-solutions 1'
        params_ged = {'lib': 'gedlibpy', 'cost': cost, 'method': 'IPFP', 
                      'algo_options': algo_options, 'stabilizer': None}
        # fit on k-graph subset
        edit_cost_constant, _, _, _, _, _, _ = fit_GED_to_kernel_distance(Gn_median, 
                node_label, edge_label, gkernel, itr_max, params_ged=params_ged, 
                init_costs=init_costs, dataset=dataset, parallel=True)
    elif fit_method == 'whole-dataset':
        itr_max = 6
        if cost == 'LETTER':
            init_costs = [0.9, 1.7, 0.75] 
        elif cost == 'LETTER2':
            init_costs = [0.675, 0.675, 0.75, 0.425, 0.425]
        else:
            init_costs = [3, 3, 1, 3, 3, 1] 
        algo_options = '--threads 1 --initial-solutions 40 --ratio-runs-from-initial-solutions 1'
        params_ged = {'lib': 'gedlibpy', 'cost': cost, 'method': 'IPFP', 
                    'algo_options': algo_options, 'stabilizer': None}
        # fit on all subset
        edit_cost_constant, _, _, _, _, _, _ = fit_GED_to_kernel_distance(Gn, 
                node_label, edge_label, gkernel, itr_max, params_ged=params_ged, 
                init_costs=init_costs, dataset=dataset, parallel=True)
    elif fit_method == 'precomputed':
        edit_cost_constant = edit_costs

    
    # compute set median and gen median using IAM (C++ through bash).
    group_fnames = [Gn[g].graph['filename'] for g in group_min]
    sod_sm, sod_gm, fname_sm, fname_gm = iam_bash(group_fnames, edit_cost_constant,
                                                  cost=cost, graph_dir=graph_dir, 
                                                  dataset=dataset)
    
    
    # compute distances in kernel space.
    Gn_median = [Gn[g].copy() for g in group_min]
    set_median = loadGXL(fname_sm)
    gen_median = loadGXL(fname_gm)
#    print(gen_median.nodes(data=True))
#    print(gen_median.edges(data=True))
    if dataset == 'letter':
        for g in Gn_median:
            reform_attributes(g)
        reform_attributes(set_median)
        reform_attributes(gen_median)
    
    # compute distance in kernel space for set median.    
    Kmatrix_sm = compute_kernel([set_median] + Gn_median, gkernel, 
                                None if dataset == 'letter' else 'chem', 
                                None if dataset == 'letter' else 'valence', 
                                False)
    dis_k_sm = dis_gstar(0, range(1, 1+len(Gn_median)), 
                         [1 / len(Gn_median)] * len(Gn_median), Kmatrix_sm, withterm3=False)
#    print(gen_median.nodes(data=True))
#    print(gen_median.edges(data=True))
#    print(set_median.nodes(data=True))
#    print(set_median.edges(data=True))
    # compute distance in kernel space for generalized median.
    Kmatrix_gm = compute_kernel([gen_median] + Gn_median, gkernel, 
                                None if dataset == 'letter' else 'chem', 
                                None if dataset == 'letter' else 'valence', 
                                False)
    dis_k_gm = dis_gstar(0, range(1, 1+len(Gn_median)), 
                         [1 / len(Gn_median)] * len(Gn_median), Kmatrix_gm, withterm3=False)
    
    # compute distance in kernel space for each graph in median set.
    dis_k_gi = []
    for idx in range(len(Gn_median)):
        dis_k_gi.append(dis_gstar(idx+1, range(1, 1+len(Gn_median)), 
                             [1 / len(Gn_median)] * len(Gn_median), Kmatrix_gm, withterm3=False))
    
    print('sod_sm:', sod_sm)
    print('sod_gm:', sod_gm)
    print('dis_k_sm:', dis_k_sm)
    print('dis_k_gm:', dis_k_gm)
    print('dis_k_gi:', dis_k_gi)
    idx_dis_k_gi_min = np.argmin(dis_k_gi)
    dis_k_gi_min = dis_k_gi[idx_dis_k_gi_min]
    print('index min dis_k_gi:', group_min[idx_dis_k_gi_min])
    print('min dis_k_gi:', dis_k_gi_min)    
    
    return sod_sm, sod_gm, dis_k_sm, dis_k_gm, dis_k_gi, dis_k_gi_min, group_min[idx_dis_k_gi_min]


def reform_attributes(G):
    for node in G.nodes:
        G.nodes[node]['attributes'] = [G.nodes[node]['x'], G.nodes[node]['y']]


def get_closest_k_graphs(dis_mat, k, parallel):
    k_graph_groups = combinations(range(0, len(dis_mat)), k)
    sod_ks_min = np.inf
    if parallel:
        len_combination = get_combination_length(len(dis_mat), k)
        len_itr_max = int(len_combination if len_combination < 1e7 else 1e7)
#        pos_cur = 0
        graph_groups_slices = split_iterable(k_graph_groups, len_itr_max, len_combination)
        for graph_groups_cur in graph_groups_slices:
#        while True:
#            graph_groups_cur = islice(k_graph_groups, pos_cur, pos_cur + len_itr_max)
            graph_groups_cur_list = list(graph_groups_cur) 
            print('current position:', graph_groups_cur_list[0])
            len_itr_cur = len(graph_groups_cur_list)
#            if len_itr_cur < len_itr_max:
#                break

            itr = zip(graph_groups_cur_list, range(0, len_itr_cur))
            sod_k_list = np.empty(len_itr_cur)
            graphs_list = [None] * len_itr_cur
            n_jobs = multiprocessing.cpu_count()
            chunksize = int(len_itr_max / n_jobs + 1)
            n_jobs = multiprocessing.cpu_count()
            def init_worker(dis_mat_toshare):
                global G_dis_mat
                G_dis_mat = dis_mat_toshare
            pool = Pool(processes=n_jobs, initializer=init_worker, initargs=(dis_mat,))
#            iterator = tqdm(pool.imap_unordered(_get_closest_k_graphs_parallel, 
#                                                itr, chunksize),
#                            desc='Choosing k closest graphs', file=sys.stdout)
            iterator = pool.imap_unordered(_get_closest_k_graphs_parallel, itr, chunksize)
            for graphs, i, sod_ks in iterator:
                sod_k_list[i] = sod_ks
                graphs_list[i] = graphs
            pool.close()
            pool.join()
            
            arg_min = np.argmin(sod_k_list)
            sod_ks_cur = sod_k_list[arg_min]
            group_cur = graphs_list[arg_min]
            if sod_ks_cur < sod_ks_min:
                sod_ks_min = sod_ks_cur
                group_min = group_cur
                print('get closer graphs:', sod_ks_min, group_min)
    else:        
        for items in tqdm(k_graph_groups, desc='Choosing k closest graphs', file=sys.stdout):
    #        if items[0] != itmp:
    #            itmp = items[0]
    #            print(items)
            k_graph_pairs = combinations(items, 2)
            sod_ks = 0
            for i1, i2 in k_graph_pairs:
                sod_ks += dis_mat[i1, i2]
            if sod_ks < sod_ks_min:
                sod_ks_min = sod_ks
                group_min = items
                print('get closer graphs:', sod_ks_min, group_min)
                
    return sod_ks_min, group_min


def _get_closest_k_graphs_parallel(itr):
    k_graph_pairs = combinations(itr[0], 2)
    sod_ks = 0
    for i1, i2 in k_graph_pairs:
        sod_ks += G_dis_mat[i1, i2]

    return itr[0], itr[1], sod_ks
    

def split_iterable(iterable, n, len_iter):
    it = iter(iterable)
    for i in range(0, len_iter, n):
        piece = islice(it, n)
        yield piece


def get_combination_length(n, k):
    len_combination = 1
    for i in range(n, n - k, -1):
        len_combination *= i
    return int(len_combination / math.factorial(k))


###############################################################################

def test_k_closest_graphs():
    ds = {'name': 'monoterpenoides', 
          'dataset': '../datasets/monoterpenoides/dataset_10+.ds'}  # node/edge symb
    Gn, y_all = loadDataset(ds['dataset'])
#    Gn = Gn[0:50]
#    gkernel = 'untilhpathkernel'
#    gkernel = 'weisfeilerlehmankernel'
    gkernel = 'treeletkernel'
    node_label = 'atom'
    edge_label = 'bond_type'
    
    k = 5
    edit_costs = [0.16229209837639536, 0.06612870523413916, 0.04030113378793905, 0.20723547009415202, 0.3338607220394598, 0.27054392518077297]
    
#    sod_sm, sod_gm, dis_k_sm, dis_k_gm, dis_k_gi, dis_k_gi_min \
#        = median_on_k_closest_graphs(Gn, node_label, edge_label, gkernel, k, 
#                                     'precomputed', edit_costs=edit_costs, 
##                                     'k-graphs',
#                                     parallel=False)
#        
#    sod_sm, sod_gm, dis_k_sm, dis_k_gm, dis_k_gi, dis_k_gi_min \
#        = median_on_k_closest_graphs(Gn, node_label, edge_label, gkernel, k, 
#                                     'expert', parallel=False)
        
    sod_sm, sod_gm, dis_k_sm, dis_k_gm, dis_k_gi, dis_k_gi_min \
        = median_on_k_closest_graphs(Gn, node_label, edge_label, gkernel, k, 
                                     'expert', parallel=False)
    return


def test_k_closest_graphs_with_cv():
    gkernel = 'untilhpathkernel'
    node_label = 'atom'
    edge_label = 'bond_type'
    
    k = 4
    
    y_all = ['3', '1', '4', '6', '7', '8', '9', '2']
    repeats = 50
    collection_path = '/media/ljia/DATA/research-repo/codes/others/gedlib/tests_linlin/generated_datsets/monoterpenoides/'
    graph_dir = collection_path + 'gxl/'
    
    sod_sm_list = []
    sod_gm_list = []
    dis_k_sm_list = []
    dis_k_gm_list = []
    dis_k_gi_min_list = []
    for y in y_all:
        print('\n-------------------------------------------------------')
        print('class of y:', y)
        
        sod_sm_list.append([])
        sod_gm_list.append([])
        dis_k_sm_list.append([])
        dis_k_gm_list.append([])
        dis_k_gi_min_list.append([])
    
        for repeat in range(repeats):
            print('\nrepeat ', repeat)
            collection_file = collection_path + 'monoterpenoides_' + y + '_' + str(repeat) + '.xml'
            Gn, _ = loadDataset(collection_file, extra_params=graph_dir)
            sod_sm, sod_gm, dis_k_sm, dis_k_gm, dis_k_gi, dis_k_gi_min \
                = median_on_k_closest_graphs(Gn, node_label, edge_label, gkernel, 
                                             k, 'whole-dataset', graph_dir=graph_dir,
                                             parallel=False)
            
            sod_sm_list[-1].append(sod_sm)
            sod_gm_list[-1].append(sod_gm)
            dis_k_sm_list[-1].append(dis_k_sm)
            dis_k_gm_list[-1].append(dis_k_gm)
            dis_k_gi_min_list[-1].append(dis_k_gi_min)
            
        print('\nsods of the set median for this class:', sod_sm_list[-1])
        print('\nsods of the gen median for this class:', sod_gm_list[-1])
        print('\ndistances in kernel space of set median for this class:', 
              dis_k_sm_list[-1])
        print('\ndistances in kernel space of gen median for this class:', 
              dis_k_gm_list[-1])
        print('\ndistances in kernel space of min graph for this class:', 
              dis_k_gi_min_list[-1])
        
        sod_sm_list[-1] = np.mean(sod_sm_list[-1])
        sod_gm_list[-1] = np.mean(sod_gm_list[-1])
        dis_k_sm_list[-1] = np.mean(dis_k_sm_list[-1])
        dis_k_gm_list[-1] = np.mean(dis_k_gm_list[-1])
        dis_k_gi_min_list[-1] = np.mean(dis_k_gi_min_list[-1])
        
    print()
    print('\nmean sods of the set median for each class:', sod_sm_list)
    print('\nmean sods of the gen median for each class:', sod_gm_list)
    print('\nmean distance in kernel space of set median for each class:', 
          dis_k_sm_list)
    print('\nmean distances in kernel space of gen median for each class:', 
          dis_k_gm_list)
    print('\nmean distances in kernel space of min graph for each class:', 
          dis_k_gi_min_list)
    
    print('\nmean sods of the set median of all:', np.mean(sod_sm_list))
    print('\nmean sods of the gen median of all:', np.mean(sod_gm_list))
    print('\nmean distances in kernel space of set median of all:', 
            np.mean(dis_k_sm_list))
    print('\nmean distances in kernel space of gen median of all:', 
            np.mean(dis_k_gm_list))
    print('\nmean distances in kernel space of min graph of all:', 
            np.mean(dis_k_gi_min_list))
    
    return
    

if __name__ == '__main__':
    test_k_closest_graphs()
#    test_k_closest_graphs_with_cv()