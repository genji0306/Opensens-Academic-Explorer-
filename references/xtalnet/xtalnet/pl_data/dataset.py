import hydra
import omegaconf
import torch
import pandas as pd
from omegaconf import ValueNode
from torch.utils.data import Dataset
import os
from torch_geometric.data import Data
import pickle
import numpy as np
from scipy.signal import find_peaks
from tqdm import tqdm

from xtalnet.common.utils import PROJECT_ROOT
from xtalnet.common.data_utils import (
    preprocess, preprocess_tensors, add_scaled_lattice_prop, preprocess_mof, LMDBDataset)


class CrystMOFLMDBDataset(Dataset):
    def __init__(self, name: ValueNode, path: ValueNode, use_pxrd: ValueNode, is_training: ValueNode,
                 **kwargs):
        super().__init__()
        self.path = path
        self.name = name
        self.use_pxrd = use_pxrd
        self.is_training = is_training

        self.cached_data = LMDBDataset(path)

        self.cut_off(400)

    def cut_off(self, n):
        data_list = []
        for data in tqdm(self.cached_data):
            if data['atoms_num'] <= n:
                data_list.append(data)
        self.cached_data = data_list

    def __len__(self) -> int:
        return len(self.cached_data)

    def __getitem__(self, index):
        data_dict = self.cached_data[index]


        frac_coords = np.array(data_dict['atom_frac_pos'])
        atom_types = np.array(data_dict['atom_type'])
        num_atoms = (data_dict['atoms_num'])
        lengths = np.array(data_dict['parameters'][:3])
        angles = np.array(data_dict['parameters'][3:])

        # atom_coords are fractional coordinates
        # edge_index is incremented during batching
        # https://pytorch-geometric.readthedocs.io/en/latest/notes/batching.html
        data = Data(
            frac_coords=torch.Tensor(frac_coords),
            atom_types=torch.LongTensor(atom_types),
            lengths=torch.Tensor(lengths).view(1, -1),
            angles=torch.Tensor(angles).view(1, -1),
            idx=index,
            num_atoms=num_atoms,
            num_nodes=num_atoms,  # special attribute used for batching in pytorch geometric
        )

        if self.use_pxrd:
            data.pxrd_x = torch.tensor(data_dict['x']).view(-1,1)
            data.pxrd_y = torch.tensor(data_dict['y']).view(-1,1)
            data.pxrd_y = (data.pxrd_y-data.pxrd_y.min()) / data.pxrd_y.max()
            pxrd_y_array = data.pxrd_y.cpu().numpy().reshape(-1)
            peaks = find_peaks(pxrd_y_array, height=0.01, prominence=0.02)[0]
            data.peak_x = torch.from_numpy(peaks).long().view(-1, 1) # nx1
            data.peak_y = torch.from_numpy(pxrd_y_array[peaks]).view(-1, 1)
            data.peak_n = len(data.peak_x)

        return data

    def __repr__(self) -> str:
        return f"CrystMOFLMDBDataset({self.name=}, {self.path=})"



class CrystMOFDataset(Dataset):
    def __init__(self, name: ValueNode, path: ValueNode,
                 prop: ValueNode, niggli: ValueNode, primitive: ValueNode,
                 graph_method: ValueNode, preprocess_workers: ValueNode,
                 lattice_scale_method: ValueNode, save_path: ValueNode, tolerance: ValueNode, use_space_group: ValueNode, use_pos_index: ValueNode, use_pxrd: ValueNode,
                 **kwargs):
        super().__init__()
        self.path = path
        self.name = name
        self.prop = prop
        self.niggli = niggli
        self.primitive = primitive
        self.graph_method = graph_method
        self.lattice_scale_method = lattice_scale_method
        self.use_space_group = use_space_group
        self.use_pos_index = use_pos_index
        self.tolerance = tolerance
        self.use_pxrd = use_pxrd

        self.preprocess(save_path, preprocess_workers, prop)

        self.cut_off(400)

    def cut_off(self, n):
        data_list = []
        for data in self.cached_data:
            if data['graph_arrays'][-1] < n:
                data_list.append(data)
        self.cached_data = data_list
    
    def preprocess(self, save_path, preprocess_workers, prop):
        if os.path.exists(save_path):
            self.cached_data = torch.load(save_path)
        else:
            cached_data = preprocess_mof(
            self.path,
            preprocess_workers,
            niggli=self.niggli,
            primitive=self.primitive,
            graph_method=self.graph_method,
            prop_list=[prop],
            use_space_group=self.use_space_group,
            tol=self.tolerance)
            torch.save(cached_data, save_path)
            self.cached_data = cached_data

    def __len__(self) -> int:
        return len(self.cached_data)

    def __getitem__(self, index):
        data_dict = self.cached_data[index]

        # scaler is set in DataModule set stage
        (frac_coords, atom_types, lengths, angles, edge_indices,
         to_jimages, num_atoms) = data_dict['graph_arrays']

        # atom_coords are fractional coordinates
        # edge_index is incremented during batching
        # https://pytorch-geometric.readthedocs.io/en/latest/notes/batching.html
        data = Data(
            frac_coords=torch.Tensor(frac_coords),
            atom_types=torch.LongTensor(atom_types),
            lengths=torch.Tensor(lengths).view(1, -1),
            angles=torch.Tensor(angles).view(1, -1),
            edge_index=torch.LongTensor(
                edge_indices.T).contiguous(),  # shape (2, num_edges)
            to_jimages=torch.LongTensor(to_jimages),
            num_atoms=num_atoms,
            num_bonds=edge_indices.shape[0],
            num_nodes=num_atoms,  # special attribute used for batching in pytorch geometric
        )

        if self.use_pxrd:
            data.pxrd_x = torch.tensor(data_dict['pxrd_x']).view(-1,1)
            data.pxrd_y = torch.tensor(data_dict['pxrd_y']).view(-1,1)
            data.pxrd_y = data.pxrd_y / data.pxrd_y.max()
            pxrd_y_array = data.pxrd_y.cpu().numpy().reshape(-1)
            peaks = find_peaks(pxrd_y_array)[0]
            data.peak_x = torch.from_numpy(peaks).long().view(-1, 1) # nx1
            data.peak_y = torch.from_numpy(pxrd_y_array[peaks]).view(-1, 1)
            data.peak_n = len(data.peak_x)

        if self.use_space_group:
            data.spacegroup = torch.LongTensor([data_dict['spacegroup']])
            data.ops = torch.Tensor(data_dict['wyckoff_ops'])
            data.anchor_index = torch.LongTensor(data_dict['anchors'])

        if self.use_pos_index:
            pos_dic = {}
            indexes = []
            for atom in atom_types:
                pos_dic[atom] = pos_dic.get(atom, 0) + 1
                indexes.append(pos_dic[atom] - 1)
            data.index = torch.LongTensor(indexes)
        return data

    def __repr__(self) -> str:
        return f"CrystMOFDataset({self.name=}, {self.path=})"


@hydra.main(config_path=str(PROJECT_ROOT / "conf"), config_name="default")
def main(cfg: omegaconf.DictConfig):
    from torch_geometric.data import Batch
    from xtalnet.common.data_utils import get_scaler_from_data_list
    dataset: CrystMOFLMDBDataset = hydra.utils.instantiate(
        cfg.data.datamodule.datasets.train, _recursive_=False
    )
    lattice_scaler = get_scaler_from_data_list(
        dataset.cached_data,
        key='scaled_lattice')
    scaler = get_scaler_from_data_list(
        dataset.cached_data,
        key=dataset.prop)

    dataset.lattice_scaler = lattice_scaler
    dataset.scaler = scaler
    data_list = [dataset[i] for i in range(len(dataset))]
    batch = Batch.from_data_list(data_list)
    return batch


if __name__ == "__main__":
    main()
