from pathlib import Path
from typing import Any, List
import sys
import os
import logging

from pytorch_lightning.utilities.types import STEP_OUTPUT
sys.path.append('.')
import hydra
import numpy as np
import torch
import omegaconf
import pytorch_lightning as pl
from hydra.core.hydra_config import HydraConfig
from omegaconf import DictConfig, OmegaConf
from pytorch_lightning import LightningModule, Trainer, seed_everything, Callback
from pytorch_lightning.callbacks import (
    EarlyStopping,
    LearningRateMonitor,
    ModelCheckpoint,
)
from pytorch_lightning.loggers import WandbLogger, CSVLogger, TensorBoardLogger

from xtalnet.common.utils import log_hyperparameters, PROJECT_ROOT

import wandb


class ConsoleLogging(Callback):

    def __init__(self,):
        super().__init__()
        self.logger = logging.getLogger("ConsoleLogging")

    def on_train_batch_end(self, trainer: Trainer, pl_module: LightningModule, outputs: STEP_OUTPUT, batch: Any, batch_idx: int) -> None:
        super().on_train_batch_end(trainer, pl_module, outputs, batch, batch_idx)
        if trainer.local_rank==0 and batch_idx % 50 == 0:
            met = trainer.callback_metrics
            epoch_int = trainer.current_epoch
            msg = ""
            for k, v in met.items():
                if "loss" in k:
                    msg += f'{k}: {v:.4f}, '
            self.logger.info(f'Epoch {epoch_int}, batch {batch_idx}: {msg}')


def build_callbacks(cfg: DictConfig) -> List[Callback]:
    callbacks: List[Callback] = []

    if "lr_monitor" in cfg.logging:
        hydra.utils.log.info("Adding callback <LearningRateMonitor>")
        callbacks.append(
            LearningRateMonitor(
                logging_interval=cfg.logging.lr_monitor.logging_interval,
                log_momentum=cfg.logging.lr_monitor.log_momentum,
            )
        )

    if "early_stopping" in cfg.train:
        hydra.utils.log.info("Adding callback <EarlyStopping>")
        callbacks.append(
            EarlyStopping(
                monitor=cfg.train.monitor_metric,
                mode=cfg.train.monitor_metric_mode,
                patience=cfg.train.early_stopping.patience,
                verbose=cfg.train.early_stopping.verbose,
            )
        )

    if "model_checkpoints" in cfg.train:
        hydra.utils.log.info("Adding callback <ModelCheckpoint>")
        callbacks.append(
            ModelCheckpoint(
                dirpath=Path(HydraConfig.get().run.dir),
                monitor=cfg.train.monitor_metric,
                mode=cfg.train.monitor_metric_mode,
                save_top_k=-1,
                verbose=cfg.train.model_checkpoints.verbose,
                save_last=cfg.train.model_checkpoints.save_last,
                every_n_epochs=5
            )
        )
    
    callbacks.append(ConsoleLogging())

    return callbacks


def run(cfg: DictConfig) -> None:
    """
    Generic train loop

    :param cfg: run configuration, defined by Hydra in /conf
    """
    if cfg.train.deterministic:
        seed_everything(cfg.train.random_seed)

    # Hydra run directory
    hydra_dir = Path(HydraConfig.get().run.dir)

    # Instantiate datamodule
    hydra.utils.log.info(f"Instantiating <{cfg.data.datamodule._target_}>")
    datamodule: pl.LightningDataModule = hydra.utils.instantiate(
        cfg.data.datamodule, _recursive_=False
    )

    # Instantiate model
    hydra.utils.log.info(f"Instantiating <{cfg.model._target_}>")
    model: pl.LightningModule = hydra.utils.instantiate(
        cfg.model,
        optim=cfg.optim,
        data=cfg.data,
        logging=cfg.logging,
        _recursive_=False,
    )

    # Instantiate the callbacks
    callbacks: List[Callback] = build_callbacks(cfg=cfg)

    # Logger instantiation/configuration
    wandb_logger = None
    if "wandb" in cfg.logging:
        hydra.utils.log.info("Instantiating <WandbLogger>")
        wandb_config = cfg.logging.wandb
        os.makedirs(wandb_config.save_dir, exist_ok=True)
        wandb_logger = WandbLogger(
            **wandb_config,
            settings=wandb.Settings(start_method="fork"),
            tags=cfg.core.tags,
        )
        hydra.utils.log.info("W&B is now watching <{cfg.logging.wandb_watch.log}>!")
        wandb_logger.watch(
            model,
            log=cfg.logging.wandb_watch.log,
            log_freq=cfg.logging.wandb_watch.log_freq,
        )
    csv_logger = None
    if "csv" in cfg.logging:
        hydra.utils.log.info("Instantiating <CSVLogger>")
        csv_logger = CSVLogger(
            save_dir=hydra_dir,
            name=cfg.logging.csv.name,
            flush_logs_every_n_steps=50
        )
    os.makedirs(hydra_dir / "tsb", exist_ok=True)
    tensorboard_logger = TensorBoardLogger(hydra_dir / "tsb", name=cfg.expname)

    # Store the YaML config separately into the wandb dir
    yaml_conf: str = OmegaConf.to_yaml(cfg=cfg)
    (hydra_dir / "hparams.yaml").write_text(yaml_conf)
          
    hydra.utils.log.info("Instantiating the Trainer")
    trainer = pl.Trainer(
        default_root_dir=hydra_dir,
        logger=[wandb_logger, csv_logger, tensorboard_logger],
        callbacks=callbacks,
        deterministic=cfg.train.deterministic,
        val_check_interval=1.0,
        **cfg.train.pl_trainer,
    )

    log_hyperparameters(trainer=trainer, model=model, cfg=cfg)

    hydra.utils.log.info("Starting training!")
    trainer.fit(model=model, datamodule=datamodule)

    hydra.utils.log.info("Starting testing!")
    trainer.test(datamodule=datamodule)

    # Logger closing to release resources/avoid multi-run conflicts
    if wandb_logger is not None:
        wandb_logger.experiment.finish()


@hydra.main(version_base=None, config_path=str(PROJECT_ROOT / "conf"), config_name="default")
def main(cfg: omegaconf.DictConfig):
    run(cfg)


if __name__ == "__main__":
    main()
