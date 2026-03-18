import torch
import torch.nn.functional as F
import numpy as np
import argparse

def main(args):
    data = torch.load(args.root_path)
    pxrd_feat = []
    atom_feat = []
    atom_type_list = []
    atom_pos_list = []
    for i in range(len(data['atom_feat'])):
        pxrd_feat.append(data['pxrd_feat'][i].squeeze(0))
        atom_feat.append(data['atom_feat'][i].squeeze(0))
        atom_type_list.append(data['atom_types'][i].squeeze(0))
        atom_pos_list.append(data['frac_coords'][i].squeeze(0))
    pxrd_tensor = torch.cat(pxrd_feat, dim=0)
    atom_tensor = torch.cat(atom_feat, dim=0)
    per_pxrd = pxrd_tensor @ atom_tensor.T
    prop_sort = torch.argsort(per_pxrd, dim=1, descending=True)
    sort_num = []
    for i in range(prop_sort.shape[0]):
        sort_num.append((prop_sort[i]==i).nonzero().item())
    print("mean corret sequence num: ",np.mean(sort_num))
    label = torch.arange(per_pxrd.shape[0], device=per_pxrd.device)
    print("cross entropy: ", F.cross_entropy(per_pxrd, label))
    top1_idx = per_pxrd.topk(1, dim=1)[1].squeeze()
    top1_rate = (top1_idx==torch.arange(per_pxrd.shape[0], device=per_pxrd.device)).sum().item()/per_pxrd.shape[0]
    print("top 1 rate: ", top1_rate)
    top5_idx = per_pxrd.topk(5, dim=1)[1]
    top10_idx = per_pxrd.topk(10, dim=1)[1]
    top3_idx = per_pxrd.topk(3, dim=1)[1]
    top3_hit = 0
    for idx,t in enumerate(top3_idx):
        if idx in t:
            top3_hit += 1
    print("top 3 rate: ",top3_hit/per_pxrd.shape[0])
    top5_hit = 0
    for idx,t in enumerate(top5_idx):
        if idx in t:
            top5_hit += 1
    print("top 5 rate: ",top5_hit/per_pxrd.shape[0])
    top10_hit = 0
    for idx,t in enumerate(top10_idx):
        if idx in t:
            top10_hit += 1
    print("top 10 rate: ",top10_hit/per_pxrd.shape[0])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root_path', required=True)
    args = parser.parse_args()
    main(args)
