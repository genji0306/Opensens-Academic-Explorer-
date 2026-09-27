"""Offline-only MVE perceiver. Replay metadata is simulated, never vendor evidence."""

from mve.perceiver.adapter import perceive, PerceptionResult
from mve.perceiver.contract import ImageInput
from mve.perceiver.replay import Replay

__all__ = ["perceive", "PerceptionResult", "ImageInput", "Replay"]
