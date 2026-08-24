"""OpenOutreach desktop application.

A system tray application that runs the outreach automation daemon locally,
using the user's residential IP and real browser while connecting to the
centralized AWS backend.
"""

from openoutreach.desktop.__version__ import __version__

__all__ = ["__version__"]
