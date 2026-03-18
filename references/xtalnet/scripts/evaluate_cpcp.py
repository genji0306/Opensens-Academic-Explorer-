import time
import argparse
import torch

from tqdm import tqdm
from torch.optim import Adam
from pathlib import Path
from types import SimpleNamespace
from torch_geometric.data import Batch

from eval_utils import lattices_to_params_shape, load_model_ckpt

from pymatgen.core.structure import Structure
from pymatgen.core.lattice import Lattice
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from pyxtal.symmetry import Group

import copy

import numpy as np


def diffusion(loader, model):

    frac_coords = []
    num_atoms = []
    atom_types = []
    lattices = []
    input_data_list = []
    pxrd_feat = []
    atom_feat = []
    for idx, batch in enumerate(loader):

        if torch.cuda.is_available():
            batch.cuda()
        batch_pxrd_feat = []
        batch_atom_feat = []
        batch_frac_coords, batch_num_atoms, batch_atom_types = [], [], []
        batch_lattices = []

        print(f'batch {idx} / {len(loader)}')
        outputs = model.inference(batch)
        batch_frac_coords.append(outputs['frac_coords'].detach().cpu())
        batch_num_atoms.append(outputs['num_atoms'].detach().cpu())
        batch_atom_types.append(outputs['atom_types'].detach().cpu())
        batch_lattices.append(outputs['lattices'].detach().cpu())
        batch_pxrd_feat.append(outputs['pxrd_feat'].detach().cpu())
        batch_atom_feat.append(outputs['atom_feat'].detach().cpu())

        frac_coords.append(torch.stack(batch_frac_coords, dim=0))
        num_atoms.append(torch.stack(batch_num_atoms, dim=0))
        atom_types.append(torch.stack(batch_atom_types, dim=0))
        lattices.append(torch.stack(batch_lattices, dim=0))
        pxrd_feat.append(torch.stack(batch_pxrd_feat, dim=0))
        atom_feat.append(torch.stack(batch_atom_feat, dim=0))
        input_data_list = input_data_list + batch.to_data_list()

    lattices_ = torch.cat(lattices, dim=1)
    lengths, angles = lattices_to_params_shape(lattices_)
    input_data_batch = Batch.from_data_list(input_data_list)


    return (
        frac_coords, atom_types, lattices, lengths, angles, num_atoms, input_data_batch, pxrd_feat, atom_feat
    )



def main(args):
    model_path = Path(args.model_path)
    model, test_loader, cfg = load_model_ckpt(
        model_path, args.ckpt_path, load_data=True, testing=True)

    if torch.cuda.is_available():
        model.to('cuda')
    model.eval()


    print('Evaluate the cpcp module.')


    start_time = time.time()
    (frac_coords, atom_types, lattices, lengths, angles, num_atoms, input_data_batch, pxrd_feat, atom_feat) = diffusion(
        test_loader, model)

    if args.label == '':
        diff_out_name = 'eval_diff.pt'
    else:
        diff_out_name = f'eval_diff_{args.label}.pt'

    save_path = Path(args.save_path)
    torch.save({
        'eval_setting': args,
        'input_data_batch': input_data_batch,
        'frac_coords': frac_coords,
        'num_atoms': num_atoms,
        'atom_types': atom_types,
        'lattices': lattices,
        'lengths': lengths,
        'angles': angles,
        'time': time.time() - start_time,
        'pxrd_feat': pxrd_feat,
        'atom_feat': atom_feat
    }, save_path / diff_out_name)    

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model_path', required=True)
    parser.add_argument('--ckpt_path', required=True)
    parser.add_argument('--save_path', required=True)
    parser.add_argument('--label', default='')
    
    args = parser.parse_args()
    main(args)