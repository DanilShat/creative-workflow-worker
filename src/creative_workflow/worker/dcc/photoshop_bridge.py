"""Post-Gate-A Photoshop bridge boundary.

The worker exposes the contract surface now, but it reports unavailable unless
a real Photoshop UXP bridge is configured. This prevents simulated DCC completion
from satisfying Gate A.
"""

from creative_workflow.shared.enums import FailureType
from creative_workflow.worker.browser.flows.base import BrowserFlowError


class PhotoshopBridge:
    def execute(self, _job):
        raise BrowserFlowError(FailureType.PHOTOSHOP_NOT_CONNECTED, "Photoshop bridge is not connected in Gate A.")
