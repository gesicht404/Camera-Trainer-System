import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QPixmap

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from camera import CaptureResultPanel


def test_starts_in_idle_state_with_ready_message(qapp):
    panel = CaptureResultPanel()
    assert panel.state == "idle"
    assert "Ready to capture" in panel.message_label.text()
    assert panel.image_label.isHidden()


def test_show_capturing_sets_capturing_state_and_hides_image(qapp):
    panel = CaptureResultPanel()
    panel.show_capturing()
    assert panel.state == "capturing"
    assert "Capturing" in panel.message_label.text()
    assert panel.image_label.isHidden()


def test_show_result_sets_success_state_and_displays_image(qapp):
    panel = CaptureResultPanel()
    pixmap = QPixmap(4, 4)

    panel.show_result(pixmap)

    assert panel.state == "success"
    assert not panel.image_label.isHidden()
    assert not panel.image_label.pixmap().isNull()
    assert panel.message_label.isHidden()


def test_show_error_sets_error_state_with_message(qapp):
    panel = CaptureResultPanel()
    panel.show_error("USB connection lost")

    assert panel.state == "error"
    assert "USB connection lost" in panel.message_label.text()
    assert panel.image_label.isHidden()


def test_show_result_scales_pixmap_to_image_label_actual_box(qapp):
    panel = CaptureResultPanel()
    panel.resize(320, 400)
    panel.show()
    QCoreApplication.processEvents()

    panel.show_result(QPixmap(100, 100))
    QCoreApplication.processEvents()

    expected = QPixmap(100, 100).scaled(
        panel.image_label.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
    )
    assert panel.image_label.pixmap().size() == expected.size()
    # the label fills the panel exactly (no layout margin drift), so the scale target is the full panel.
    assert panel.image_label.size() == panel.size()


def test_show_idle_after_result_clears_image(qapp):
    panel = CaptureResultPanel()
    panel.show_result(QPixmap(4, 4))

    panel.show_idle()

    assert panel.state == "idle"
    assert panel.image_label.isHidden()
