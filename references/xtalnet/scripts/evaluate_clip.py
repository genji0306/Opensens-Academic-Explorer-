import time
import argparse
import torch

from tqdm import tqdm
from torch.optim import Adam
from pathlib import Path
from types import SimpleNamespace
from torch_geometric.data import Batch
from pytorch_lightning import seed_everything

from eval_utils import (
    load_clip_model,
    lattices_to_params_shape,
    load_dataset,
    lattices_to_params_shape,
)

import json, os
import torch.nn.functional as F
import copy

import numpy as np

def get_metrics(pxrd_tensor, atom_tensor):
    result = {}
    per_pxrd = pxrd_tensor @ atom_tensor.T
    prop_sort = torch.argsort(per_pxrd, dim=1, descending=True)
    sort_num = []
    for i in range(prop_sort.shape[0]):
        sort_num.append((prop_sort[i]==i).nonzero().item())
    result['mean_correct_sequence_num'] = np.mean(sort_num)
    print("mean corret sequence num: ",np.mean(sort_num))
    label = torch.arange(per_pxrd.shape[0], device=per_pxrd.device)
    result['cross_entropy'] = F.cross_entropy(per_pxrd, label).item()
    print("cross entropy: ", F.cross_entropy(per_pxrd, label))
    top1_idx = per_pxrd.topk(1, dim=1)[1].squeeze()
    top1_rate = (top1_idx==torch.arange(per_pxrd.shape[0], device=per_pxrd.device)).sum().item()/per_pxrd.shape[0]
    result['top1_rate'] = top1_rate
    print("top 1 rate: ", top1_rate)
    top5_idx = per_pxrd.topk(5, dim=1)[1]
    top10_idx = per_pxrd.topk(10, dim=1)[1]
    top3_idx = per_pxrd.topk(3, dim=1)[1]
    top3_hit = 0
    for idx,t in enumerate(top3_idx):
        if idx in t:
            top3_hit += 1
    result['top3_rate'] = (top3_hit/per_pxrd.shape[0])
    print("top 3 rate: ",top3_hit/per_pxrd.shape[0])
    top5_hit = 0
    for idx,t in enumerate(top5_idx):
        if idx in t:
            top5_hit += 1
    result['top5_rate'] = (top5_hit/per_pxrd.shape[0])
    print("top 5 rate: ",top5_hit/per_pxrd.shape[0])
    top10_hit = 0
    for idx,t in enumerate(top10_idx):
        if idx in t:
            top10_hit += 1
    result['top10_rate'] = (top10_hit/per_pxrd.shape[0])
    print("top 10 rate: ",top10_hit/per_pxrd.shape[0])
    return result
    
@torch.no_grad()
def test(
    loader,
    clip_model,
):
    input_data_list = []
    pxrd_feat_list, atom_feat_list = [], []
    for idx, batch in tqdm(enumerate(loader), total=len(loader)):

        if torch.cuda.is_available():
            batch.cuda()
        out_dict = clip_model.inference(batch)
        pxrd_feat = out_dict['pxrd_feat']
        atom_feat = out_dict['atom_feat']
        pxrd_feat_list.append(pxrd_feat.detach().cpu())
        atom_feat_list.append(atom_feat.detach().cpu())
        input_data_list = input_data_list + batch.to_data_list()
    pxrd_tensor = torch.cat(pxrd_feat_list, dim=0)
    atom_tensor = torch.cat(atom_feat_list, dim=0)

    return pxrd_tensor, atom_tensor, input_data_list


def main(args):
    seed_everything(42)
    # load_data if do reconstruction.
    test_loader = load_dataset(
        args.data_hydra_config_path, args.data_name
    )
    clip_model = load_clip_model(args.clip_hydra_config_path, args.clip_ckpt_path)
    clip_model.eval()
    if torch.cuda.is_available():
        clip_model.to("cuda")

    print("Evaluate the clip model.")

    start_time = time.time()
    pxrd_tensor, atom_tensor, input_data_list = test(
        test_loader,
        clip_model,
    )
    metrics = get_metrics(pxrd_tensor, atom_tensor)

    if args.label == "":
        out_name = f"eval_{args.data_name}_clip.pt"
    else:
        out_name = f"eval_{args.data_name}_clip_{args.label}.pt"

    torch.save(
        {
            "eval_setting": args,
            "pxrd_tensor": pxrd_tensor,
            "atom_tensor": atom_tensor,
            "input_data_list": input_data_list,
            "metrics": metrics,
        },
        Path(args.save_path) / out_name,
    )
    metrics_out_file = Path(args.save_path) / f"clip_{args.data_name}_metrics.json"

    # only overwrite metrics computed in the new run.
    with open(metrics_out_file, 'w') as f:
        json.dump(metrics, f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--clip_hydra_config_path",
        default="/vepfs/fs_users/qingsi/lqs_ws/pxrd2d3/DiffCSP/conf/model",
    )
    parser.add_argument(
        "--data_hydra_config_path",
        default="/vepfs/fs_users/qingsi/lqs_ws/pxrd2d3/DiffCSP/conf",
    )
    parser.add_argument("--clip_ckpt_path", default='/vepfs/fs_users/qingsi/lqs_ws/xtalnet/hydra/singlerun/2023-12-12/hmof_only_clip/new_epoch=458-step=526014.ckpt')
    parser.add_argument("--data_name",default="hmof_100")
    parser.add_argument("--save_path",default='/vepfs/fs_users/qingsi/lqs_ws/xtalnet/hydra/singlerun/2024-01-06/0106_full_hmof_onlyclip_400_bsz4_lr_2e-4')
    parser.add_argument("--label", default="hmof_100_clip_eval")
    args = parser.parse_args()
    main(args)
