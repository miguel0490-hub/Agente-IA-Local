"""Tests de resolución de assets en bundles HTML+CSS+JS."""

from __future__ import annotations

from pathlib import Path

from src.services.file_factory import FileFactory
from src.services.web_bundle import patch_html_asset_links, patch_html_content, resolve_asset_ref


def test_resolve_prefixed_css_and_js(tmp_path: Path):
    (tmp_path / "834ee3cd_style.css").write_text("body{}", encoding="utf-8")
    (tmp_path / "eb20e6c7_app.js").write_text("console.log(1)", encoding="utf-8")

    assert resolve_asset_ref("style.css", tmp_path) == "834ee3cd_style.css"
    assert resolve_asset_ref("app.js", tmp_path) == "eb20e6c7_app.js"


def test_patch_html_content_rewrites_links(tmp_path: Path):
    (tmp_path / "abc123_style.css").write_text("h1{}", encoding="utf-8")
    html = '<link rel="stylesheet" href="style.css"><script src="app.js"></script>'
    (tmp_path / "abc123_app.js").write_text("", encoding="utf-8")

    out = patch_html_content(html, tmp_path)
    assert 'href="abc123_style.css"' in out
    assert 'src="abc123_app.js"' in out


def test_patch_html_asset_links_updates_file(tmp_path: Path):
    (tmp_path / "ff_style.css").write_text("", encoding="utf-8")
    html_path = tmp_path / "index.html"
    html_path.write_text('<link href="style.css">', encoding="utf-8")

    assert patch_html_asset_links(html_path) is True
    assert 'href="ff_style.css"' in html_path.read_text(encoding="utf-8")


def test_order_tools_puts_html_last():
    from src.services.web_bundle import order_tools_for_web_bundle

    tools = [
        {"action": "create_file", "filename": "index.html"},
        {"action": "create_file", "filename": "style.css"},
        {"action": "search_web", "query": "x"},
        {"action": "create_file", "filename": "app.js"},
    ]
    ordered = order_tools_for_web_bundle(tools)
    names = [t["filename"] for t in ordered if t.get("action") == "create_file"]
    assert names == ["style.css", "app.js", "index.html"]


def test_find_broken_asset_refs(tmp_path: Path):
    from src.services.web_bundle import find_broken_asset_refs

    html = tmp_path / "index.html"
    html.write_text('<link href="missing.css"><script src="app.js"></script>', encoding="utf-8")
    (tmp_path / "app.js").write_text("", encoding="utf-8")
    assert find_broken_asset_refs(html) == ["missing.css"]


def test_file_factory_web_assets_without_uuid_prefix(tmp_path: Path):
    factory = FileFactory(output_dir=str(tmp_path))
    css_path = factory.execute_tool(
        {"action": "create_file", "filename": "style.css", "content": "body{}"}
    )
    assert css_path
    assert Path(css_path).name == "style.css"
