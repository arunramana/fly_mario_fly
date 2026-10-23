"""Helpers shared by the senses (not plug-ins: the registry skips sub-packages).

geom      the geometry every sense measures with (angle, 2-D gap, "cleared", Mario's eye)
memory    the per-sense memory object the runner hands to cue()
world     what the whole frame looks like to a sense (object kinds, floor-standing walls)
headroom  how far a jump can lift Mario's head before a ceiling stops it
draw      colours and the OverlayItem / CalcStep builders, so every sense speaks the same visual language
"""
