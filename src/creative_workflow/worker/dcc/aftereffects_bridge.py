"""Post-Gate-A After Effects bridge boundary."""

from creative_workflow.shared.enums import FailureType
from creative_workflow.worker.browser.flows.base import BrowserFlowError


class AfterEffectsBridge:
    def execute(self, _job):
        raise BrowserFlowError(FailureType.AFTEREFFECTS_NOT_CONNECTED, "After Effects bridge is not connected in Gate A.")

