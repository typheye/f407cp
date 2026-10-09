"""BasicVin detector debug page entry point.

The detector implementation remains in ``depends.gray_detection`` so camera
and image-processing code stays reusable, while the application imports the
page from the UI package consistently.
"""

from depends.gray_detection import GrayDetector


class GrayDetectionPage(GrayDetector):
    """Embedded Host-compatible BasicVin debug page."""

    pass
