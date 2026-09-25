"""tool/ui/widgets/neuron_activity_strip.py -- BARS: a small, fixed set of
per-population activations, each with a MEASURED max value (tool/core/
display_params.py's own PreviewBarParams, tool/SCALARS_UI.md) rather than
a uniform guess -- found in manual testing that a uniform 5.0 pinned TTMn
at 100% the instant it fired, since a jump's TTMn value is exactly
SPIKE_AMP, "a spike is a full-scale event", 10x the old assumed ceiling.
TTMn's own max reads config.jump.spike_amp directly rather than a
duplicate display scalar.

Used to also hold NeuronActivityStrip, a persistent horizontal bar widget
under the Run tab's preview -- removed in the Run tab / player redesign
(the Data overlay's own compact readout, tool/ui/widgets/
run_data_overlay.py, replaces it, reusing this same BARS table for its
"top active neurons" ranking rather than re-deriving a second set of
ceilings).
"""

from __future__ import annotations

from config.params import JumpParams
from tool.core.display_params import PreviewBarParams

# (telemetry key, display label, max value for the bar) -- see this
# module's own docstring for where the max values come from.
_bars = PreviewBarParams()
BARS = [
    ("lc4", "LC4", _bars.bar_max_lc4),
    ("lplc2", "LPLC2", _bars.bar_max_lplc2),
    ("ttmn", "TTMn", JumpParams().spike_amp),
    ("dna01", "DNa01", _bars.bar_max_dna01),
    ("dna02", "DNa02", _bars.bar_max_dna02),
    ("dnp09", "DNp09", _bars.bar_max_dnp09),
    ("mdn", "MDN", _bars.bar_max_mdn),
]
