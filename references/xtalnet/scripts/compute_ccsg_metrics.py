from collections import Counter
import argparse
import os
import json
import pdb
import multiprocessing as mp
import numpy as np
from pathlib import Path
from tqdm import tqdm
from p_tqdm import p_map, t_map
from scipy.stats import wasserstein_distance
import pandas as pd

from pymatgen.core.structure import Structure
from pymatgen.core.composition import Composition
from pymatgen.core.lattice import Lattice
from pymatgen.analysis.structure_matcher import StructureMatcher
from matminer.featurizers.site.fingerprint import CrystalNNFingerprint
from matminer.featurizers.composition.composite import ElementProperty

from pyxtal import pyxtal

import torch

import sys
sys.path.append('.')

from eval_utils import (
    smact_validity, structure_validity, CompScaler, get_fp_pdist,
    load_config, load_data, get_crystals_list, compute_cov)

CrystalNNFP = CrystalNNFingerprint.from_preset("ops")
CompFP = ElementProperty.from_preset('magpie')


class Crystal(object):

    def __init__(self, crys_array_dict):
        self.frac_coords = crys_array_dict['frac_coords']
        self.atom_types = crys_array_dict['atom_types']
        self.lengths = crys_array_dict['lengths']
        self.angles = crys_array_dict['angles']
        self.dict = crys_array_dict
        if len(self.atom_types.shape) > 1:
            self.dict['atom_types'] = (np.argmax(self.atom_types, axis=-1) + 1)
            self.atom_types = (np.argmax(self.atom_types, axis=-1) + 1)

        self.get_structure()
        self.get_composition()
        self.get_validity()


    def get_structure(self):
        if min(self.lengths.tolist()) < 0:
            self.constructed = False
            self.invalid_reason = 'non_positive_lattice'
        if np.isnan(self.lengths).any() or np.isnan(self.angles).any() or  np.isnan(self.frac_coords).any():
            self.constructed = False
            self.invalid_reason = 'nan_value'            
        else:
            try:
                self.structure = Structure(
                    lattice=Lattice.from_parameters(
                        *(self.lengths.tolist() + self.angles.tolist())),
                    species=self.atom_types, coords=self.frac_coords, coords_are_cartesian=False)
                self.constructed = True
            except Exception:
                self.constructed = False
                self.invalid_reason = 'construction_raises_exception'
            if self.structure.volume < 0.1:
                self.constructed = False
                self.invalid_reason = 'unrealistically_small_lattice'

    def get_composition(self):
        elem_counter = Counter(self.atom_types)
        composition = [(elem, elem_counter[elem])
                       for elem in sorted(elem_counter.keys())]
        elems, counts = list(zip(*composition))
        counts = np.array(counts)
        counts = counts / np.gcd.reduce(counts)
        self.elems = elems
        self.comps = tuple(counts.astype('int').tolist())

    def get_validity(self):
        self.comp_valid = True
        if self.constructed:
            self.struct_valid = structure_validity(self.structure)
        else:
            self.struct_valid = False
        self.struct_valid = True
        self.valid = self.comp_valid and self.struct_valid


class RecEval(object):

    def __init__(self, pred_crys, gt_crys, stol=0.7, angle_tol=5, ltol=0.2):
        assert len(pred_crys) == len(gt_crys)
        self.matcher = StructureMatcher(
            stol=stol, angle_tol=angle_tol, ltol=ltol)
        self.preds = pred_crys
        self.gts = gt_crys

    def get_match_rate_and_rms(self):
        def process_one(pred, gt, is_valid):
            if not is_valid:
                return None
            try:
                rms_dist = self.matcher.get_rms_dist(
                    pred.structure, gt.structure)
                rms_dist = None if rms_dist is None else rms_dist[0]
                return rms_dist
            except Exception:
                return None
        validity = [c1.valid and c2.valid for c1,c2 in zip(self.preds, self.gts)]
        rms_dists = []
        for i in tqdm(range(len(self.preds))):
            rms_dists.append(process_one(
                self.preds[i], self.gts[i], validity[i]))
        rms_dists = np.array(rms_dists)
        match_rate = sum(rms_dists != None) / len(self.preds)
        mean_rms_dist = rms_dists[rms_dists != None].mean()
        return {'match_rate': match_rate,
                'rms_dist': mean_rms_dist,
                'rms_dists':rms_dists}     

    def get_metrics(self):
        metrics = {}
        metrics.update(self.get_match_rate_and_rms())
        return metrics

def process_one(pred, gt, matcher):
    try:
        rms_dist = matcher.get_rms_dist(
            pred.structure, gt.structure)
        rms_dist = None if rms_dist is None else rms_dist[0]
        return rms_dist
    except Exception:
        return None

def process_batch(preds, gt, matcher):
    rms_dists = np.zeros(len(preds))
    for i in (range(len(preds))):
        rms_dists[i] = (process_one(
            preds[i], gt, matcher))
    if np.isnan(rms_dists).all():
        return rms_dists, None
    else:
        return rms_dists, np.nanmin(rms_dists)

class RecEvalBatch(object):
#0.7, 5, 0.2
    def __init__(self, pred_crys, gt_crys, rank=None, stol=0.9, angle_tol=10, ltol=0.3, bsz=10000):
        self.matcher = StructureMatcher(
            stol=stol, angle_tol=angle_tol, ltol=ltol)
        self.preds = pred_crys
        self.gts = gt_crys
        self.batch_size = min(len(self.preds), bsz)
        self.rank = rank.cpu().numpy() if rank is not None else None

    def get_randomk_match_rate_and_rms(self, dists, k=1):
        all_dists = np.array(dists)[:k, :]
        rmse_list = []
        for i in range(len(all_dists[0])):
            if (np.isnan(all_dists[:, i])).all():
                pass
            else:
                rmse_list.append(np.nanmin(all_dists[:, i]))
        match_rate = len(rmse_list) / len(all_dists[0])
        mean_rms_dist = np.mean(rmse_list)
        return {'match_rate': match_rate,
                'rms_dist': mean_rms_dist}
    
    def get_match_rate_and_rms(self):
        def process_one(pred, gt, is_valid):
            if not is_valid:
                return None
            try:
                rms_dist = self.matcher.get_rms_dist(
                    pred.structure, gt.structure)
                rms_dist = None if rms_dist is None else rms_dist[0]
                return rms_dist
            except Exception:
                return None

        rms_dists = []
        self.all_rms_dis = np.zeros((self.batch_size, len(self.gts)))
        for i in tqdm(range(len(self.preds[0]))):
            tmp_rms_dists = []
            for j in range(self.batch_size):
                if i==199 and j==7:
                    rmsd = None
                else:
                    rmsd = process_one(self.preds[j][i], self.gts[i], self.preds[j][i].valid)
                self.all_rms_dis[j][i] = rmsd
                if rmsd is not None:
                    tmp_rms_dists.append(rmsd)
            if len(tmp_rms_dists) == 0:
                rms_dists.append(None)
            else:
                rms_dists.append(np.min(tmp_rms_dists))
        
        result = {}
        rms_dists = np.array(rms_dists)
        match_rate = sum(rms_dists != None) / len(self.preds[0])
        mean_rms_dist = rms_dists[rms_dists != None].mean()
        result['match_rate'] = match_rate
        result['rms_dist'] = mean_rms_dist
        
        for i in [1,3,5,10]:
            if i > len(self.preds[0]):
                break
            result[f'match_rate_random_{i}'] = self.get_randomk_match_rate_and_rms(self.all_rms_dis, k=i)['match_rate']
            result[f'rms_dist_random_{i}'] = self.get_randomk_match_rate_and_rms(self.all_rms_dis, k=i)['rms_dist']
        if self.rank is not None:
            self.rank_all_rms_dist = np.take_along_axis(np.transpose(self.all_rms_dis, (1,0)), self.rank, axis=1)
            result['rank_all_rms_dist'] = self.rank_all_rms_dist
            for i in [1,3,5,10]:
                rms_dists_i = self.rank_all_rms_dist[:, :i]
                min_rmse = []
                for j in range(len(rms_dists_i)):
                    if (np.isnan(rms_dists_i[j])).all():
                        pass
                    else:
                        min_rmse.append(np.nanmin(rms_dists_i[j]))
                match_rate_i = len(min_rmse) / len(self.preds[0])
                mean_rms_dist_i = np.mean(min_rmse)
                result[f'match_rate_top_{i}'] = match_rate_i
                result[f'rms_dist_top_{i}'] = mean_rms_dist_i
        
        return result  

    def get_metrics(self):
        metrics = {}
        metrics.update(self.get_match_rate_and_rms())
        return metrics

def get_file_paths(root_path, task, label='', suffix='pt'):
    if args.label == '':
        out_name = f'eval_{task}.{suffix}'
    else:
        out_name = f'eval_{task}_{label}.{suffix}'
    out_name = os.path.join(root_path, out_name)
    return out_name


def get_crystal_array_list(file_path, batch_idx=0):
    data = load_data(file_path)
    if batch_idx == -1:
        batch_size = data['frac_coords'].shape[0]
        crys_array_list = []
        for i in range(batch_size):
            tmp_crys_array_list = get_crystals_list(
                data['frac_coords'][i],
                data['atom_types'][i],
                data['lengths'][i],
                data['angles'][i],
                data['num_atoms'][i])
            crys_array_list.append(tmp_crys_array_list)
    elif batch_idx == -2:
        crys_array_list = get_crystals_list(
            data['frac_coords'],
            data['atom_types'],
            data['lengths'],
            data['angles'],
            data['num_atoms'])        
    else:
        crys_array_list = get_crystals_list(
            data['frac_coords'][batch_idx],
            data['atom_types'][batch_idx],
            data['lengths'][batch_idx],
            data['angles'][batch_idx],
            data['num_atoms'][batch_idx])

    if 'input_data_batch' in data:
        batch = data['input_data_batch']
        if isinstance(batch, dict):
            true_crystal_array_list = get_crystals_list(
                batch['frac_coords'], batch['atom_types'], batch['lengths'],
                batch['angles'], batch['num_atoms'])
        else:
            true_crystal_array_list = get_crystals_list(
                batch.frac_coords, batch.atom_types, batch.lengths,
                batch.angles, batch.num_atoms)
    else:
        true_crystal_array_list = None

    return crys_array_list, true_crystal_array_list


def get_gt_crys_ori(cif):
    structure = Structure.from_str(cif,fmt='cif')
    lattice = structure.lattice
    crys_array_dict = {
        'frac_coords':structure.frac_coords,
        'atom_types':np.array([_.Z for _ in structure.species]),
        'lengths': np.array(lattice.abc),
        'angles': np.array(lattice.angles)
    }
    return Crystal(crys_array_dict) 

def main(args):
    all_metrics = {}

    recon_file_path = args.root_path
    batch_idx = -1 if args.multi_eval else 0
    crys_array_list, true_crystal_array_list = get_crystal_array_list(
        recon_file_path, batch_idx = batch_idx)
    data = load_data(recon_file_path)
    gt_crys = t_map(lambda x: Crystal(x), true_crystal_array_list)

    if not args.multi_eval:
        pred_crys = p_map(lambda x: Crystal(x), crys_array_list)
    else:
        pred_crys = []
        for i in range(min(len(crys_array_list), args.bsz)):
            print(f"Processing batch {i}")
            pred_crys.append(t_map(lambda x: Crystal(x), crys_array_list[i]))   

    if args.multi_eval:
        if 'res_rank' in data and len(data['res_rank']) > 0:
            rank = data['res_rank']
        elif 'score_list' in data:
            score_list = data['score_list']
            score_list = torch.cat(score_list, dim=1).cpu().transpose(1,0)
            rank = torch.argsort(score_list, dim=1, descending=True)
        else:
            rank = None
        rec_evaluator = RecEvalBatch(pred_crys, gt_crys,  rank, bsz=args.bsz)
    else:
        rec_evaluator = RecEval(pred_crys, gt_crys)

    recon_metrics = rec_evaluator.get_metrics()

    all_metrics.update(recon_metrics)

    rms_dists = all_metrics.pop('rms_dists', None)
    rank_all_rms_dist = all_metrics.pop('rank_all_rms_dist', None)
    print(all_metrics)
    if rms_dists is not None:
        np.save(os.path.join(args.save_path, f'rms_dists_{args.label}.npy'), rms_dists)
    if rank_all_rms_dist is not None:
        np.save(os.path.join(args.save_path, f'rank_all_rms_dist_{args.label}.npy'), rank_all_rms_dist)
    if args.label == '':
        metrics_out_file = 'eval_metrics.json'
    else:
        metrics_out_file = f'eval_metrics_{args.label}.json'
    metrics_out_file = os.path.join(args.save_path, metrics_out_file)

    # only overwrite metrics computed in the new run.
    if Path(metrics_out_file).exists():
        with open(metrics_out_file, 'r') as f:
            written_metrics = json.load(f)
            if isinstance(written_metrics, dict):
                written_metrics.update(all_metrics)
            else:
                with open(metrics_out_file, 'w') as f:
                    json.dump(all_metrics, f)
        if isinstance(written_metrics, dict):
            with open(metrics_out_file, 'w') as f:
                json.dump(written_metrics, f)
    else:
        with open(metrics_out_file, 'w') as f:
            json.dump(all_metrics, f)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root_path', required=True)
    parser.add_argument('--save_path', required=True)
    parser.add_argument('--label', default='')
    parser.add_argument('--multi_eval',action='store_true')
    parser.add_argument("--bsz", default='10000', type=int)
    args = parser.parse_args()
    main(args)
