import copy
import os
import numpy as np
import torch
import hydra

from scipy.spatial.distance import pdist
from scipy.spatial.distance import cdist
from scipy.signal import find_peaks
from hydra.experimental import compose
from hydra import initialize_config_dir
from pathlib import Path

import sys
sys.path.append('.')

from xtalnet.common.constants import CompScalerMeans, CompScalerStds
from xtalnet.common.data_utils import StandardScaler, chemical_symbols
from xtalnet.pl_data.datamodule import worker_init_fn

from pymatgen.core import Composition, Element, Lattice, Structure
from torch_geometric.data import Batch, Data
from pytorch_lightning import seed_everything

CompScaler = StandardScaler(
    means=np.array(CompScalerMeans),
    stds=np.array(CompScalerStds),
    replace_nan_token=0.)

import pdb


def lattices_to_params_shape(lattices):

    lengths = torch.sqrt(torch.sum(lattices ** 2, dim=-1))
    angles = torch.zeros_like(lengths)
    for i in range(3):
        j = (i + 1) % 3
        k = (i + 2) % 3
        angles[...,i] = torch.clamp(torch.sum(lattices[...,j,:] * lattices[...,k,:], dim = -1) /
                            (lengths[...,j] * lengths[...,k]), -1., 1.)
    angles = torch.arccos(angles) * 180.0 / np.pi

    return lengths, angles

def load_data(file_path):
    if file_path[-3:] == 'npy':
        data = np.load(file_path, allow_pickle=True).item()
        for k, v in data.items():
            if k == 'input_data_batch':
                for k1, v1 in data[k].items():
                    data[k][k1] = torch.from_numpy(v1)
            else:
                data[k] = torch.from_numpy(v).unsqueeze(0)
    else:
        data = torch.load(file_path, map_location='cpu')
    return data


def get_model_path(eval_model_name):
    import xtalnet
    model_path = (
        Path(xtalnet.__file__).parent / 'prop_models' / eval_model_name)
    return model_path


def load_config(model_path):
    with initialize_config_dir(str(model_path)):
        cfg = compose(config_name='hparams')
    return cfg

def load_dataset(hydra_path, data_name):
    with initialize_config_dir(str(hydra_path)):
        cfg = compose(config_name='default', overrides=[f'data={data_name}'])
        cfg.data.datamodule.batch_size.test = 1
        datamodule = hydra.utils.instantiate(
                cfg.data.datamodule, _recursive_=False
            )
        datamodule.setup('test')
        test_loader = datamodule.test_dataloader()[0]

    return test_loader

def load_model_ckpt(model_path, ckpt_path, load_data=False, testing=True):
    with initialize_config_dir(str(model_path)):
        cfg = compose(config_name='hparams')
        model = hydra.utils.get_class(
            cfg.model._target_,
        )
        model = model.load_from_checkpoint(ckpt_path, strict=True)

        if load_data:
            cfg.data.datamodule.batch_size.test = 1
            datamodule = hydra.utils.instantiate(
                cfg.data.datamodule, _recursive_=False, scaler_path=model_path
            )
            if testing:
                datamodule.setup('test')
                test_loader = datamodule.test_dataloader()[0]
            else:
                datamodule.setup()
                train_loader = datamodule.train_dataloader(shuffle=False)
                val_loader = datamodule.val_dataloader()[0]
                test_loader = (train_loader, val_loader)
        else:
            test_loader = None

    return model, test_loader, cfg


def get_crystals_list(
        frac_coords, atom_types, lengths, angles, num_atoms):
    """
    args:
        frac_coords: (num_atoms, 3)
        atom_types: (num_atoms)
        lengths: (num_crystals)
        angles: (num_crystals)
        num_atoms: (num_crystals)
    """
    assert frac_coords.size(0) == atom_types.size(0) == num_atoms.sum()
    assert lengths.size(0) == angles.size(0) == num_atoms.size(0)

    start_idx = 0
    crystal_array_list = []
    for batch_idx, num_atom in enumerate(num_atoms.tolist()):
        cur_frac_coords = frac_coords.narrow(0, start_idx, num_atom)
        cur_atom_types = atom_types.narrow(0, start_idx, num_atom)
        cur_lengths = lengths[batch_idx]
        cur_angles = angles[batch_idx]

        crystal_array_list.append({
            'frac_coords': cur_frac_coords.detach().cpu().numpy(),
            'atom_types': cur_atom_types.detach().cpu().numpy(),
            'lengths': cur_lengths.detach().cpu().numpy(),
            'angles': cur_angles.detach().cpu().numpy(),
        })
        start_idx = start_idx + num_atom
    return crystal_array_list




def structure_validity(crystal, cutoff=0.5):
    dist_mat = crystal.distance_matrix
    # Pad diagonal with a large number
    dist_mat = dist_mat + np.diag(
        np.ones(dist_mat.shape[0]) * (cutoff + 10.))
    if dist_mat.min() < cutoff or crystal.volume < 0.1 or max(crystal.lattice.abc) > 40:
        return False
    else:
        return True


def get_fp_pdist(fp_array):
    if isinstance(fp_array, list):
        fp_array = np.array(fp_array)
    fp_pdists = pdist(fp_array)
    return fp_pdists.mean()




def filter_fps(struc_fps, comp_fps):
    assert len(struc_fps) == len(comp_fps)

    filtered_struc_fps, filtered_comp_fps = [], []

    for struc_fp, comp_fp in zip(struc_fps, comp_fps):
        if struc_fp is not None and comp_fp is not None:
            filtered_struc_fps.append(struc_fp)
            filtered_comp_fps.append(comp_fp)
    return filtered_struc_fps, filtered_comp_fps


def compute_cov(crys, gt_crys,
                struc_cutoff, comp_cutoff, num_gen_crystals=None):
    struc_fps = [c.struct_fp for c in crys]
    comp_fps = [c.comp_fp for c in crys]
    gt_struc_fps = [c.struct_fp for c in gt_crys]
    gt_comp_fps = [c.comp_fp for c in gt_crys]

    assert len(struc_fps) == len(comp_fps)
    assert len(gt_struc_fps) == len(gt_comp_fps)

    # Use number of crystal before filtering to compute COV
    if num_gen_crystals is None:
        num_gen_crystals = len(struc_fps)

    struc_fps, comp_fps = filter_fps(struc_fps, comp_fps)

    comp_fps = CompScaler.transform(comp_fps)
    gt_comp_fps = CompScaler.transform(gt_comp_fps)

    struc_fps = np.array(struc_fps)
    gt_struc_fps = np.array(gt_struc_fps)
    comp_fps = np.array(comp_fps)
    gt_comp_fps = np.array(gt_comp_fps)

    struc_pdist = cdist(struc_fps, gt_struc_fps)
    comp_pdist = cdist(comp_fps, gt_comp_fps)

    struc_recall_dist = struc_pdist.min(axis=0)
    struc_precision_dist = struc_pdist.min(axis=1)
    comp_recall_dist = comp_pdist.min(axis=0)
    comp_precision_dist = comp_pdist.min(axis=1)

    cov_recall = np.mean(np.logical_and(
        struc_recall_dist <= struc_cutoff,
        comp_recall_dist <= comp_cutoff))
    cov_precision = np.sum(np.logical_and(
        struc_precision_dist <= struc_cutoff,
        comp_precision_dist <= comp_cutoff)) / num_gen_crystals

    metrics_dict = {
        'cov_recall': cov_recall,
        'cov_precision': cov_precision,
        'amsd_recall': np.mean(struc_recall_dist),
        'amsd_precision': np.mean(struc_precision_dist),
        'amcd_recall': np.mean(comp_recall_dist),
        'amcd_precision': np.mean(comp_precision_dist),
    }

    combined_dist_dict = {
        'struc_recall_dist': struc_recall_dist.tolist(),
        'struc_precision_dist': struc_precision_dist.tolist(),
        'comp_recall_dist': comp_recall_dist.tolist(),
        'comp_precision_dist': comp_precision_dist.tolist(),
    }

    return metrics_dict, combined_dist_dict

def get_pred_structure(batch_idx, idx, data, offset=[0.5,0.5,0.5]):
    crystal_array_list = get_crystals_list(
            data['frac_coords'][batch_idx],
            data['atom_types'][batch_idx],
            data['lengths'][batch_idx],
            data['angles'][batch_idx],
            data['num_atoms'][batch_idx])
    pred = crystal_array_list[idx]['frac_coords']
    a,b,c = crystal_array_list[idx]['lengths']
    alpha, beta, gamma = crystal_array_list[idx]['angles']
    atom_type = crystal_array_list[idx]['atom_types']
    coords = pred +  np.array(offset).reshape(-1,3)
    coords = coords - np.floor(coords)
    lattice = Lattice.from_parameters(a=a, b=b, c=c, alpha=alpha,
                                    beta=beta, gamma=gamma)
    pred_struct = Structure(lattice, atom_type, coords)
    return pred_struct, data['rank'][batch_idx]

def diffusion_gradio(
    batch,
    ccsg_model,
    cpcp_model,
    num_evals,
    step_lr=1e-5,
):
    frac_coords = []
    num_atoms = []
    atom_types = []
    lattices = []
    input_data_list = []
    pxrd_feat, atom_feat = [], []
    score_list = []

    if torch.cuda.is_available():
        batch.cuda()
    batch_frac_coords, batch_num_atoms, batch_atom_types = [], [], []
    batch_lattices = []
    atom_feat_i = []
    input_data_list = input_data_list + batch.to_data_list()
    
    for eval_idx in range(num_evals):
        print(f"sample {eval_idx} / {num_evals}")
        outputs, _ = ccsg_model.sample(batch, step_lr=step_lr)
        batch_frac_coords.append(outputs["frac_coords"].detach().cpu())
        batch_num_atoms.append(outputs["num_atoms"].detach().cpu())
        batch_atom_types.append(outputs["atom_types"].detach().cpu())
        batch_lattices.append(outputs["lattices"].detach().cpu())

        new_batch = copy.deepcopy(batch)
        new_batch.frac_coords = outputs["frac_coords"]
        new_batch.lengths, new_batch.angles = lattices_to_params_shape(
            outputs["lattices"]
        )
        atom_feat_i.append(
            cpcp_model.inference(new_batch)["atom_feat"].detach().cpu()
        )
    pxrd_feat_i = cpcp_model.inference(new_batch)["pxrd_feat"].detach().cpu()
    atom_feat_i = torch.stack(atom_feat_i, dim=0)
    score_list.append(torch.cosine_similarity(atom_feat_i, pxrd_feat_i, dim=-1))
    atom_feat.append(atom_feat_i)
    pxrd_feat.append(pxrd_feat_i)
    frac_coords.append(torch.stack(batch_frac_coords, dim=0))
    num_atoms.append(torch.stack(batch_num_atoms, dim=0))
    atom_types.append(torch.stack(batch_atom_types, dim=0))
    lattices.append(torch.stack(batch_lattices, dim=0))

    frac_coords = torch.cat(frac_coords, dim=1)
    num_atoms = torch.cat(num_atoms, dim=1)
    atom_types = torch.cat(atom_types, dim=1)
    lattices = torch.cat(lattices, dim=1)
    lengths, angles = lattices_to_params_shape(lattices)
    input_data_batch = Batch.from_data_list(input_data_list)

    return dict(
        frac_coords=frac_coords,
        num_atoms=num_atoms,
        atom_types=atom_types,
        lattices=lattices,
        lengths=lengths,
        angles=angles,
        input_data_batch=input_data_batch,
        atom_feat=atom_feat,
        pxrd_feat=pxrd_feat,
        score_list=score_list,
        rank=torch.argsort(torch.cat(score_list).reshape(-1)),
    )
    
def construct_input(text, pxrd_x, pxrd_y):
    pxrd_y = (pxrd_y-np.min(pxrd_y)) / np.max(pxrd_y)
    peaks = find_peaks(pxrd_y, height=0.01, prominence=0.02)[0]
    peak_x = torch.from_numpy(peaks).long().view(-1, 1) # nx1
    peak_y = torch.from_numpy(pxrd_y[peaks]).view(-1, 1)
    peak_n = len(peak_x)
    
    comp = Composition(text)
    atom_types = []
    for el, num in comp.items():
        el = Element(el)
        atom_types += [el.Z for i in range(int(num))]
    atom_types = torch.LongTensor(atom_types)
    num_nodes = len(atom_types)
    
    data_input = Data(
                atom_types=atom_types,
                peak_x=peak_x,
                peak_y=peak_y,
                peak_n=peak_n,
                num_nodes=num_nodes,
                num_atoms=num_nodes,
            )
    batch_data = Batch.from_data_list([data_input])
    return batch_data

def get_model_gradio(ccsg_ckpt_path, cpcp_ckpt_path):
    seed_everything(42)
    ccsg_model_path = Path(os.path.dirname(ccsg_ckpt_path))
    ccsg_model, _, _ = load_model_ckpt(
        ccsg_model_path, ccsg_ckpt_path, load_data=False
    )
    ccsg_model.eval()
    cpcp_model_path = Path(os.path.dirname(cpcp_ckpt_path))
    cpcp_model, _, _ = load_model_ckpt(cpcp_model_path, cpcp_ckpt_path)
    cpcp_model.eval()
    if torch.cuda.is_available():
        ccsg_model.to("cuda")
        cpcp_model.to("cuda")
    return ccsg_model, cpcp_model

def get_eval_gradio(data_input, ccsg_model, cpcp_model, save_path, num_evals):
    seed_everything(42)
    out_dict = diffusion_gradio(
        data_input,
        ccsg_model,
        cpcp_model,
        num_evals=num_evals,
        step_lr=1e-5,
    )
    
    out_path = []
    for i in range(num_evals):
        s, rank = get_pred_structure(i, 0, out_dict)
        s.to(f'{save_path}/data_rank_{rank}.cif')
        out_path.append(f'{save_path}/data_rank_{rank}.cif')
    return out_path
