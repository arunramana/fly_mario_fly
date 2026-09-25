"""tool/ui/widgets/preview.py -- frame-drawing helpers shared by the Run
tab's video player (tool/ui/widgets/video_player.py): converting a raw NES
RGB frame to a QPixmap, and scaling it up by a whole-number factor with
nearest-neighbour sampling so pixel art stays crisp instead of turning to
mush under a smooth filter.

Used to also hold PreviewWidget, the pre-redesign live-preview widget --
removed once VideoPlayer's own live mode took over its one caller
(tool/ui/tabs/run.py); these two functions are the part of it still used.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPixmap

NES_W, NES_H = 256, 240


def frame_to_pixmap(frame: np.ndarray) -> QPixmap:
    frame = np.ascontiguousarray(frame)
    h, w, _ = frame.shape
    image = QImage(frame.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(image.copy())  # copy: `frame` may be freed/reused after this call


def integer_scale(pixmap: QPixmap, target: QSize) -> QPixmap:
    """Scales UP by the largest whole-number factor that still fits
    `target`, nearest-neighbour -- pixel art stays crisp instead of soft
    (a smooth filter) or needlessly tiny (no scale-up at all). Never
    scales down below 1x: a target smaller than the source just shows the
    source at native size, since shrinking pixel art is the one direction
    that never looks better."""
    if pixmap.isNull() or target.width() <= 0 or target.height() <= 0:
        return pixmap
    factor = max(1, min(target.width() // pixmap.width(), target.height() // pixmap.height()))
    return pixmap.scaled(pixmap.width() * factor, pixmap.height() * factor,
                          Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
