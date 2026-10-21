"""Draws a run: the glowing-somata brain beside the game with the sense overlay. Talks to the runner only.

    from fly_mario.render import Renderer, BrainData, FrameData
    img = Renderer(brain_data, show_senses=True, show_brain=True).frame(frame_data)     # (1080, 1920, 3) uint8

CLI: python -m fly_mario.render run <run> | montage <evolution id>   (see __main__.py)
"""
from fly_mario.render.data import BrainData, FrameData
from fly_mario.render.draw import H, W, Renderer

__all__ = ["BrainData", "FrameData", "Renderer", "W", "H"]
