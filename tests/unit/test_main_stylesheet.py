from __future__ import annotations

from probe_app.main import _interaction_stylesheet


def test_interaction_stylesheet_distinguishes_hover_press_and_primary_actions() -> None:
    stylesheet = _interaction_stylesheet()

    assert "QPushButton:hover" in stylesheet
    assert "QPushButton:pressed" in stylesheet
    assert "QPushButton:disabled" in stylesheet
    assert "#primaryOpenFolderButton" in stylesheet
    assert "#runLevel4To6Analysis" in stylesheet
    assert "#exportPreviewButton" in stylesheet
