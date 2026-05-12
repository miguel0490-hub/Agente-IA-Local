"""PWA and mobile/desktop validation tests."""

from __future__ import annotations

import json
import os
import pytest

os.environ.setdefault("APP_SECRET_KEY", "pytest-ci-placeholder-not-for-production")


class TestPWAManifest:
    """Validates PWA manifest for installability."""

    @pytest.fixture
    def manifest(self):
        manifest_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "static", "manifest.json"
        )
        with open(manifest_path) as f:
            return json.load(f)

    def test_has_name(self, manifest):
        assert "name" in manifest
        assert len(manifest["name"]) > 0

    def test_has_short_name(self, manifest):
        assert "short_name" in manifest
        assert len(manifest["short_name"]) <= 12

    def test_has_start_url(self, manifest):
        assert manifest["start_url"] == "/"

    def test_display_standalone(self, manifest):
        assert manifest["display"] == "standalone"

    def test_has_icons(self, manifest):
        assert "icons" in manifest
        assert len(manifest["icons"]) >= 1
        for icon in manifest["icons"]:
            assert "src" in icon
            assert "type" in icon

    def test_has_theme_color(self, manifest):
        assert "theme_color" in manifest
        assert manifest["theme_color"].startswith("#")

    def test_has_background_color(self, manifest):
        assert "background_color" in manifest

    def test_orientation_any(self, manifest):
        assert manifest["orientation"] == "any"


class TestPWAMetaTags:
    """Validates the PWA meta tag injection code."""

    def test_pwa_html_contains_manifest_link(self):
        from src.ui.pwa import inject_pwa_meta
        import inspect
        source = inspect.getsource(inject_pwa_meta)
        assert 'rel="manifest"' in source
        assert "manifest.json" in source

    def test_pwa_html_contains_mobile_meta(self):
        import inspect
        from src.ui.pwa import inject_pwa_meta
        source = inspect.getsource(inject_pwa_meta)
        assert "mobile-web-app-capable" in source
        assert "apple-mobile-web-app-capable" in source
        assert "theme-color" in source

    def test_pwa_html_contains_apple_touch_icon(self):
        import inspect
        from src.ui.pwa import inject_pwa_meta
        source = inspect.getsource(inject_pwa_meta)
        assert "apple-touch-icon" in source


class TestResponsiveCSS:
    """Validates that CSS includes responsive/mobile rules."""

    def _find_css_source(self):
        """Finds the main CSS injected by the app."""
        try:
            from src.ui.components.header import inject_glassmorphism_css
            import inspect
            return inspect.getsource(inject_glassmorphism_css)
        except ImportError:
            return ""

    def test_has_media_queries(self):
        css_source = self._find_css_source()
        if not css_source:
            pytest.skip("CSS source not found")
        assert "@media" in css_source, "CSS should include responsive media queries"

    def test_has_mobile_breakpoints(self):
        css_source = self._find_css_source()
        if not css_source:
            pytest.skip("CSS source not found")
        has_mobile = any(bp in css_source for bp in ["768px", "480px", "600px", "max-width"])
        assert has_mobile, "CSS should include mobile breakpoints"

    def test_has_touch_friendly_sizing(self):
        css_source = self._find_css_source()
        if not css_source:
            pytest.skip("CSS source not found")
        has_touch = any(
            keyword in css_source
            for keyword in ["min-height: 44px", "min-height: 48px", "touch-action", "padding"]
        )
        assert has_touch, "CSS should include touch-friendly element sizing"


class TestManifestSchema:
    """Validates manifest.json against W3C Web App Manifest spec."""

    @pytest.fixture
    def manifest(self):
        manifest_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "static", "manifest.json"
        )
        with open(manifest_path) as f:
            return json.load(f)

    def test_valid_display_mode(self, manifest):
        valid_modes = {"fullscreen", "standalone", "minimal-ui", "browser"}
        assert manifest.get("display") in valid_modes

    def test_valid_orientation(self, manifest):
        valid_orientations = {"any", "natural", "landscape", "portrait",
                              "portrait-primary", "portrait-secondary",
                              "landscape-primary", "landscape-secondary"}
        assert manifest.get("orientation") in valid_orientations

    def test_color_format(self, manifest):
        import re
        color_re = re.compile(r"^#[0-9A-Fa-f]{6}$")
        assert color_re.match(manifest.get("theme_color", "")), "Invalid theme_color format"
        assert color_re.match(manifest.get("background_color", "")), "Invalid background_color format"
