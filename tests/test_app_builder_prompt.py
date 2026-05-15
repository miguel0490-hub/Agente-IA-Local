"""El rol app_builder incluye reglas de bundle web, DNI, NIE y tema."""

from src.core.system_prompts import PROMPT_APP_BUILDER


def test_app_builder_prompt_includes_web_bundle_rules():
    p = PROMPT_APP_BUILDER.lower()
    assert "style.css" in p
    assert "app.js" in p
    assert "trwagmyfpdxbnjzsqvhlcke" in p
    assert "type=\"button\"" in p or "type='button'" in p or "type=button" in p


def test_app_builder_prompt_includes_persistence_and_theme():
    p = PROMPT_APP_BUILDER.lower()
    assert "localstorage" in p
    assert "#00f2fe" in p
    assert "#1e293b" in p
    assert "letra correcta" in p


def test_app_builder_prompt_includes_nie():
    p = PROMPT_APP_BUILDER.lower()
    assert "nie" in p
    assert "x1234567" in p or "prefijo" in p and "x" in p
