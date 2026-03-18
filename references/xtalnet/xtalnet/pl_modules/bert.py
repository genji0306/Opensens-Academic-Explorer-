# Copyright (c) DP Technology.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging
import argparse

import torch
import torch.nn as nn
import torch.nn.functional as F
from .transformer.transformer_encoder import TransformerEncoder, init_bert_params

import pdb


class BertModel(nn.Module):
    def __init__(self, args, max_seq_len=2048, pretrained=None):
        super().__init__()
        args.max_seq_len = max_seq_len
        base_architecture(args)
        self.args = args
        self.padding_idx = 0

        self.embed_tokens = nn.Sequential(
            nn.Linear(1, args.encoder_embed_dim),
            nn.LayerNorm(args.encoder_embed_dim),
            nn.ReLU(True),
            nn.Linear(args.encoder_embed_dim, args.encoder_embed_dim),
        )
        self.vnode_encoder = nn.Embedding(1, args.encoder_embed_dim)
        # self.masked_token = nn.Embedding(1, args.encoder_embed_dim)
        self.embed_positions = nn.Embedding(args.max_seq_len, args.encoder_embed_dim)

        self.sentence_encoder = TransformerEncoder(
            encoder_layers=args.encoder_layers,
            embed_dim=args.encoder_embed_dim,
            ffn_embed_dim=args.encoder_ffn_embed_dim,
            attention_heads=args.encoder_attention_heads,
            emb_dropout=args.emb_dropout,
            dropout=args.dropout,
            attention_dropout=args.attention_dropout,
            activation_dropout=args.activation_dropout,
            max_seq_len=args.max_seq_len,
            activation_fn=args.activation_fn,
            rel_pos=False,
            rel_pos_bins=320,
            max_rel_pos=1280,
            post_ln=args.post_ln,
        )

        self.apply(init_bert_params)


    def half(self):
        super().half()
        self.embed_tokens = self.embed_tokens.float()
        self.embed_positions = self.embed_positions.float()
        self.vnode_encoder = self.vnode_encoder.float()
        self.dtype = torch.half
        return self
    
    def bfloat16(self):
        super().bfloat16()
        self.embed_tokens = self.embed_tokens.float()
        self.embed_positions = self.embed_positions.float()
        self.vnode_encoder = self.vnode_encoder.float()
        self.regression_heads = self.regression_heads.float()
        self.dtype = torch.bfloat16
        return self

    def float(self):
        super().float()
        self.dtype = torch.float32
        return self

    def batch_input(self, batch):
        peak_x = batch.peak_x # nx1
        peak_y = batch.peak_y # nx1
        peak_num = batch.peak_n # mx1
        max_peak_num = peak_num.max()
        batch_peak_x = torch.zeros((peak_num.shape[0], max_peak_num, 1)).to(peak_x.device)
        batch_peak_y = torch.zeros((peak_num.shape[0], max_peak_num, 1)).to(peak_y.device)
        idx = 0
        for i in range(len(peak_num)):
            batch_peak_x[i, :peak_num[i]] = peak_x[idx:idx+peak_num[i]]
            batch_peak_y[i, :peak_num[i]] = peak_y[idx:idx+peak_num[i]]
            idx += peak_num[i]
        return batch_peak_x.long(), batch_peak_y
            

    def forward(self, batch):
        src_pos, src_tokens = self.batch_input(batch)
        x = self.embed_tokens(src_tokens).squeeze(-2)
        pos_embed = self.embed_positions(src_pos).squeeze(-2)
        x = x + pos_embed
        
        cls_token = self.vnode_encoder.weight.unsqueeze(0).repeat(
            src_tokens.shape[0], 1, 1
        )
        x = torch.cat([cls_token, x], dim=1)

        x = x.type(self.sentence_encoder.emb_layer_norm.weight.dtype)
        
        padding_mask = torch.zeros(x.shape[:-1]).bool().to(x.device)
        padding_mask[:, 1:] = src_tokens.eq(self.padding_idx).squeeze()
        if not padding_mask.any():
            padding_mask = None

        x = self.sentence_encoder(x, padding_mask=padding_mask)

        cls_token = x[:, 0, :]
        features = x[:, 1:, :]
        results = dict(
            features=features,
            cls_token=cls_token,
        )
        return results


def base_architecture(args):
    args.encoder_layers = getattr(args, "encoder_layers", 8)
    args.encoder_embed_dim = getattr(args, "encoder_embed_dim", 512)
    args.encoder_ffn_embed_dim = getattr(args, "encoder_ffn_embed_dim", 2048)
    args.encoder_attention_heads = getattr(args, "encoder_attention_heads", 64)
    args.dropout = getattr(args, "dropout", 0.1)
    args.emb_dropout = getattr(args, "emb_dropout", 0.1)
    args.attention_dropout = getattr(args, "attention_dropout", 0.1)
    args.activation_dropout = getattr(args, "activation_dropout", 0.0)
    args.pooler_dropout = getattr(args, "pooler_dropout", 0.0)
    args.max_seq_len = getattr(args, "max_seq_len", 2048)
    args.activation_fn = getattr(args, "activation_fn", "gelu")
    args.pooler_activation_fn = getattr(args, "pooler_activation_fn", "tanh")
    args.post_ln = getattr(args, "post_ln", False)

if __name__ == '__main__':
    pxrd_encoder = BertModel(argparse.Namespace())
    data_dict = torch.load('/vepfs/fs_ckps/qingsi/log/clip/1122-peak-clip-60w-bsz128/checkpoint_last.pt')['model']
    pxrd_encoder.load_state_dict(data_dict, strict=True)
    print('succeffully load pretrained model')

