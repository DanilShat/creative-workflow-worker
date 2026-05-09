import pytest

from creative_workflow.shared.enums import FailureType
from creative_workflow.worker.browser.flows.base import BrowserFlowError
from creative_workflow.worker.dcc.aftereffects_bridge import AfterEffectsBridge
from creative_workflow.worker.dcc.photoshop_bridge import PhotoshopBridge


def test_photoshop_bridge_reports_unavailable_in_gate_a():
    with pytest.raises(BrowserFlowError) as exc:
        PhotoshopBridge().execute(None)
    assert exc.value.failure_type == FailureType.PHOTOSHOP_NOT_CONNECTED


def test_aftereffects_bridge_reports_unavailable_in_gate_a():
    with pytest.raises(BrowserFlowError) as exc:
        AfterEffectsBridge().execute(None)
    assert exc.value.failure_type == FailureType.AFTEREFFECTS_NOT_CONNECTED
