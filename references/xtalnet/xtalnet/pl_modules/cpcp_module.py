import math, copy
from argparse import Namespace
import numpy as np

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable

from typing import Union, Iterable, List, Dict, Tuple, Optional, Any

import hydra
import omegaconf
import pytorch_lightning as pl
from torch.optim.optimizer import Optimizer
from torch_scatter import scatter
from torch_scatter.composite import scatter_softmax
from torch_geometric.utils import to_dense_adj, dense_to_sparse
from torch.utils._foreach_utils import _group_tensors_by_device_and_dtype, _has_foreach_support
from tqdm import tqdm
from lightning.pytorch.utilities import grad_norm

from xtalnet.common.utils import PROJECT_ROOT
from xtalnet.common.data_utils import (
    EPSILON, cart_to_frac_coords, mard, lengths_angles_to_volume, lattice_params_to_matrix_torch,
    frac_to_cart_coords, min_distance_sqr_pbc)

from .bert import BertModel
from .diff_utils import RegressionHead
from .cspnet_ccsg import CSPLayer, SinusoidsEmbedding

MAX_ATOMIC_NUM=100

class CSPCPCPNet(nn.Module):

    def __init__(
        self,
        hidden_dim = 128,
        latent_dim = 256,
        num_layers = 4,
        max_atoms = 100,
        act_fn = 'silu',
        dis_emb = 'sin',
        num_freqs = 10,
        edge_style = 'fc',
        cutoff = 6.0,
        max_neighbors = 20,
        ln = False,
        ip = True,
        smooth = False,
        pred_type = False
    ):
        super(CSPCPCPNet, self).__init__()

        self.ip = ip
        self.node_embedding = nn.Embedding(max_atoms, hidden_dim)
        if act_fn == 'silu':
            self.act_fn = nn.SiLU()
        if dis_emb == 'sin':
            self.dis_emb = SinusoidsEmbedding(n_frequencies = num_freqs)
        elif dis_emb == 'none':
            self.dis_emb = None
        for i in range(0, num_layers):
            self.add_module(
                "csp_layer_%d" % i, CSPLayer(hidden_dim, self.act_fn, self.dis_emb, ln=ln, ip=ip)
            )            
        self.num_layers = num_layers
        self.out_node = nn.Linear(hidden_dim, hidden_dim, bias = False)
        self.pred_type = pred_type
        self.ln = ln
        self.edge_style = edge_style
        if self.ln:
            self.final_layer_norm = nn.LayerNorm(hidden_dim)
        if self.pred_type:
            self.type_out = nn.Linear(hidden_dim, MAX_ATOMIC_NUM)

    def gen_edges(self, num_atoms, frac_coords):

        if self.edge_style == 'fc':
            lis = [torch.ones(n,n, device=num_atoms.device) for n in num_atoms]
            fc_graph = torch.block_diag(*lis)
            fc_edges, _ = dense_to_sparse(fc_graph)
            return fc_edges, (frac_coords[fc_edges[1]] - frac_coords[fc_edges[0]])

    def forward(self, atom_types, frac_coords, lattices, num_atoms, node2graph):

        edges, frac_diff = self.gen_edges(num_atoms, frac_coords)
        edge2graph = node2graph[edges[0]]
        node_features = self.node_embedding(atom_types - 1)

        for i in range(0, self.num_layers):
            node_features = self._modules["csp_layer_%d" % i](node_features, frac_coords, lattices, edges, edge2graph, frac_diff = frac_diff)

        if self.ln:
            node_features = self.final_layer_norm(node_features)

        graph_features = scatter(node_features, node2graph, dim = 0, reduce = 'mean')
        final_feat = self.out_node(graph_features)
        return final_feat

class BaseModule(pl.LightningModule):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__()
        # populate self.hparams with args and kwargs automagically!
        self.save_hyperparameters()

    def configure_optimizers(self):
        opt = hydra.utils.instantiate(
            self.hparams.optim.optimizer, params=self.parameters(), _convert_="partial"
        )
        if not self.hparams.optim.use_lr_scheduler:
            return [opt]
        scheduler = hydra.utils.instantiate(
            self.hparams.optim.lr_scheduler, optimizer=opt
        )
        return {"optimizer": opt, "lr_scheduler": scheduler, "monitor": "val_loss"}
    
    def on_before_optimizer_step(self, optimizer):
        # Compute the 2-norm for each layer
        # If using mixed precision, the gradients are already unscaled here
        # norms = grad_norm(self, norm_type=2)
        parameters = self.parameters()
        grads = [p.grad for p in parameters if p.grad is not None]
        first_device = grads[0].device
        norms = []
        foreach = None
        grouped_grads: Dict[Tuple[torch.device, torch.dtype], List[List[torch.Tensor]]] \
        = _group_tensors_by_device_and_dtype([[g.detach() for g in grads]])  # type: ignore[assignment]
        for ((device, _), [grads]) in grouped_grads.items():
            if (foreach is None or foreach) and _has_foreach_support(grads, device=device):
                norms.extend(torch._foreach_norm(grads, 2.0))
            elif foreach:
                raise RuntimeError(f'foreach=True was passed, but can\'t use the foreach API on {device.type} tensors')
            else:
                norms.extend([torch.norm(g, 2.0) for g in grads])
        total_norm = torch.norm(torch.stack([norm.to(first_device) for norm in norms]), 2.0)
        self.log_dict({'grad_norm_total': total_norm})

class CPCPModule(BaseModule):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.pxrd_encoder = BertModel(Namespace())
        self.crystal_encoder = hydra.utils.instantiate(self.hparams.crystal_encoder, _recursive_=False)
        self.logit_scale = nn.Parameter(torch.ones([1]))
    
    def inference(self, batch):
        results = self.pxrd_encoder(batch)
        pxrd_feat = results["cls_token"]
        lattices = lattice_params_to_matrix_torch(batch.lengths, batch.angles)
        atom_feat = self.crystal_encoder(batch.atom_types, batch.frac_coords, lattices, batch.num_atoms, batch.batch)
        results = {
            'num_atoms' : batch.num_atoms,
            'atom_types' : batch.atom_types,
            'frac_coords' : batch.frac_coords,
            'lattices' : lattices
        }
        pxrd_feat = F.normalize(pxrd_feat, dim=-1).float()
        atom_feat = F.normalize(atom_feat, dim=-1).float()
        logit_scale = self.logit_scale.exp().float()
        
        results['pxrd_feat'] = pxrd_feat
        results['atom_feat'] = atom_feat
        results['logit_scale'] = logit_scale
        return results
        
    def forward(self, batch):
        results = self.pxrd_encoder(batch)
        pxrd_feat = results["cls_token"]
        lattices = lattice_params_to_matrix_torch(batch.lengths, batch.angles)
        atom_feat = self.crystal_encoder(batch.atom_types, batch.frac_coords, lattices, batch.num_atoms, batch.batch)
        
        results = dict()
        pxrd_feat = F.normalize(pxrd_feat, dim=-1).float()
        atom_feat = F.normalize(atom_feat, dim=-1).float()
        logit_scale = self.logit_scale.exp().float()

        logits_per_pxrd = logit_scale * pxrd_feat @ atom_feat.T
        logits_per_atom = logit_scale * atom_feat @ pxrd_feat.T
        labels = torch.arange(pxrd_feat.shape[0], device=pxrd_feat.device, dtype=torch.long)
        pxrd_loss = F.cross_entropy(logits_per_pxrd, labels)
        atom_loss = F.cross_entropy(logits_per_atom, labels)
        total_loss = (pxrd_loss + atom_loss) / 2

        loss_dict = {
            'loss' : total_loss,
            'loss_CPCP_pxrd' : pxrd_loss,
            'loss_CPCP_atom' : atom_loss
        }
        return loss_dict
    
    def training_step(self, batch: Any, batch_idx: int) -> torch.Tensor:

        output_dict = self(batch)

        loss = output_dict['loss']
        loss_CPCP_pxrd = output_dict['loss_CPCP_pxrd']
        loss_CPCP_atom = output_dict['loss_CPCP_atom']

        self.log_dict(
            {'train_loss': loss,
            'train_loss_CPCP_pxrd': loss_CPCP_pxrd,
            'train_loss_CPCP_atom': loss_CPCP_atom},
            on_step=True,
            on_epoch=True,
            prog_bar=True,
            batch_size=1,
            sync_dist=True
        )

        if loss.isnan():
            return None

        return loss

    def validation_step(self, batch: Any, batch_idx: int) -> torch.Tensor:

        output_dict = self(batch)

        log_dict, loss = self.compute_stats(output_dict, prefix='val')

        self.log_dict(
            log_dict,
            on_step=False,
            on_epoch=True,
            prog_bar=True,
            batch_size=1,
            sync_dist=True
        )
        return loss

    def test_step(self, batch: Any, batch_idx: int) -> torch.Tensor:

        output_dict = self(batch)

        log_dict, loss = self.compute_stats(output_dict, prefix='test')

        self.log_dict(
            log_dict,
            batch_size=1,
            sync_dist=True
        )
        return loss

    def compute_stats(self, output_dict, prefix):

        loss_CPCP_atom = output_dict['loss_CPCP_atom']
        loss_CPCP_pxrd = output_dict['loss_CPCP_pxrd']
        loss = output_dict['loss']

        log_dict = {
            f'{prefix}_loss': loss,
            f'{prefix}_loss_CPCP_pxrd': loss_CPCP_pxrd,
            f'{prefix}_loss_CPCP_atom': loss_CPCP_atom
        }

        return log_dict, loss