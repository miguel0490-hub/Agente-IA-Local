"""El rol ui_designer incluye réplica visual y bundle web."""

from src.core.system_prompts import PROMPT_UI_DESIGNER


def test_ui_designer_prompt_includes_bundle_and_offline_css():
    p = PROMPT_UI_DESIGNER.lower()
    assert "index.html" in p
    assert "style.css" in p
    assert "app.js" in p
    assert "sin cdn" in p or "sin internet" in p or "offline" in p or "cdn" in p
    assert "tailwind" in p


def test_ui_designer_prompt_includes_mobile_menu_and_layout_rules():
    p = PROMPT_UI_DESIGNER.lower()
    assert "hamburguesa" in p or "header" in p and "principal" in p
    assert "backdrop" in p
    assert "margin-left" in p or "grid" in p
    assert "windows" in p or "barra de tareas" in p or "sistema operativo" in p


def test_ui_designer_prompt_ignores_os_weather_and_icons():
    p = PROMPT_UI_DESIGNER.lower()
    assert "clima" in p and ("windows" in p or "sistema" in p or "no inventes" in p)
    assert "nueva conversación" in p or "nueva conversacion" in p
    assert "+" in p or "añadir" in p


def test_ui_designer_prompt_includes_superagente_and_gemini_guidance():
    p = PROMPT_UI_DESIGNER.lower()
    assert "#00f2fe" in p
    assert "gemini" in p or "#131314" in p
    assert "clamp" in p
