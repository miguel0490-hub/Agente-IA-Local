"""Tests del flujo de vídeo Gemini entre reruns."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest


class TestGeminiVideoFlow:
    @patch("src.ui.chat.gemini_video_flow.should_poll_async_jobs", return_value=True)
    @patch("src.ui.chat.gemini_video_flow.st")
    @patch("src.ui.chat.gemini_video_flow.get_genai_client")
    def test_resolve_returns_active_files(self, mock_client_fn, mock_st, _mock_poll):
        from src.ui.chat.gemini_video_flow import _job_key, resolve_gemini_video_files

        paths = ["/tmp/v.mp4"]
        key = _job_key(paths)
        active_file = MagicMock()
        active_file.name = "files/abc"
        active_file.state = MagicMock()
        active_file.state.name = "ACTIVE"

        mock_st.session_state = {
            "_gemini_video_jobs": {
                key: [{"path": paths[0], "name": "files/abc", "file": active_file}],
            },
            f"_gemini_video_start_{key}": time.time(),
        }
        mock_st.rerun = MagicMock()
        mock_st.stop = MagicMock()

        mock_client = MagicMock()
        mock_client.files.get.return_value = active_file
        mock_client_fn.return_value = mock_client

        with patch("src.ui.chat.gemini_video_flow.os.path.exists", return_value=True):
            with patch("src.ui.chat.gemini_video_flow.os.remove") as mock_rm:
                result = resolve_gemini_video_files(paths, "key")

        assert result == [active_file]
        mock_rm.assert_called()
        assert key not in mock_st.session_state.get("_gemini_video_jobs", {})

    def test_job_key_stable(self):
        from src.ui.chat.gemini_video_flow import _job_key

        assert _job_key(["a.mp4", "b.mp4"]) == _job_key(["b.mp4", "a.mp4"])

    @patch("src.ui.chat.gemini_video_flow.st")
    @patch("src.ui.chat.gemini_video_flow.get_genai_client")
    def test_upload_phase_triggers_rerun(self, mock_client_fn, mock_st):
        from src.ui.chat.gemini_video_flow import resolve_gemini_video_files

        mock_st.session_state = {}
        mock_st.rerun = MagicMock()
        mock_st.stop = MagicMock()

        uploaded = MagicMock()
        uploaded.name = "files/new"
        uploaded.state = MagicMock()
        uploaded.state.name = "PROCESSING"
        mock_client = MagicMock()
        mock_client.files.upload.return_value = uploaded
        mock_client_fn.return_value = mock_client

        with patch("src.ui.chat.gemini_video_flow.os.path.exists", return_value=True):
            resolve_gemini_video_files(["/tmp/v.mp4"], "key")

        mock_st.rerun.assert_called_once()
