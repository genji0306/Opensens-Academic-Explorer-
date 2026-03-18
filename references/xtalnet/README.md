# End-to-End Crystal Structure Prediction from Powder X-Ray Diffraction

### Dependencies and Setup
Codes are tested on Ubuntu 20.04

Use `xtalnet.yaml` to setup the environment.
```
conda env create -f xtalnet.yaml
```

Installation time depends on the internet connection.

### Data Preparation
Download the data from [here](https://drive.google.com/drive/folders/1F76mhwzI1FVbUDYblMw-B1eJF9X1Cxc9?usp=drive_link)

Change `root_path` in `conf/data/hmof_100.yaml` and `conf/data/hmof_400.yaml` to the path of the downloaded `hmof_100` dir path and `hmof_400` dir path.

Rename the `.env.template` file into `.env` and specify the following variables.

```
PROJECT_ROOT: the absolute path of this repo
HYDRA_JOBS: the absolute path to save hydra outputs
WABDB_DIR: the absolute path to save wanbdb outputs
```

### Training
#### CPCP Module Training

```bash
export expname=cpcp_training
export model=cpcp
export data_name='hmof_100' # or 'hmof_400'
export freeze=false
export bsz=16 # 4 gpus, 8 for hmof_400
export lr=5e-4 # 2e-4 for hmof_400
export betas='[0.9,0.99]'
export eps=1e-6
export weight_decay=1e-4
bash train.sh
```

#### CCSG Module Training
```bash
export expname=ccsg_training
export model=ccsg
export data_name='hmof_100' # or 'hmof_400'
export pretrained=<cpcp_ckpt_path>
export freeze=true
export bsz=16 # 4 gpus, 4 for hmof_400
export lr=1e-3 #
export betas='[0.9,0.999]'
export eps=1e-8
export weight_decay=0
bash train.sh
```

### Evaluation

#### For CPCP Module

First generate the CPCP model's predictions
```
python scripts/evaluate_cpcp.py --model_path <ckpt_dir_path> --ckpt_path <ckpt_path> --save_path <save_path> --label <label>
```

Then compute the CPCP model's metrics
```
python scripts/compute_cpcp_metrics.py --root_path <results_path>
```

#### For CCSG Module
generate samples from trained model
```
python scripts/evaluate_ccsg.py \
    --ccsg_ckpt_path <ccsg_ckpt_path> \
    --cpcp_ckpt_path <clip_ckpt_path> \
    --save_path <save_path> \
    --label <label> --num_evals <num_evals> \
    --begin_idx <begin_idx> --end_idx <end_idx> 
```

compute metrics
```
python scripts/compute_ccsg_metrics.py --root_path <results_path> \
    --save_path <save_path> --multi_eval --label <label> \
```

#### Gradio Interface
```
python scripts/gradio_demo.py --ccsg_ckpt_path <ccsg_ckpt_path> --cpcp_ckpt_path <cpcp_ckpt_path> --save_path <save_path>
```
You can use `Cu2H8C28N6O8` and `example/case.txt` as input example.
The output will be saved in `<save_path>` dir and you can also download it from gradio web UI. The GT cif file can be found in `example/case_gt.cif`.

For the V100 GPU, it takes nearly 20 seconds to generate a sample.