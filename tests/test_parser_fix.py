"""
Test de regresión para el bug KeyError: 'src' en parse_tool_calls.
Verifica que el parser maneja correctamente HTML con atributos src y
comillas simples dentro del campo content del JSON.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.agent_tools import parse_tool_calls

def test_html_con_src_no_rompe_parser():
    """El parser NO debe lanzar KeyError cuando el HTML tiene atributos src."""
    respuesta_llm = (
        "```json\n"
        '{"action":"create_file","filename":"ui.html",'
        '"content":"<!DOCTYPE html><html lang=\'es\'><head><meta charset=\'UTF-8\'>'
        '<title>UI</title></head><body>'
        '<img src=\'logo.png\' class=\'rounded\'>'
        '<a href=\'#\'>Link</a>'
        "</body></html>\"}\n"
        "```"
    )
    try:
        clean, tools = parse_tool_calls(respuesta_llm)
        assert len(tools) == 1, f"Esperaba 1 tool, encontre {len(tools)}"
        assert tools[0]["action"] == "create_file", "action debe ser create_file"
        assert tools[0]["filename"] == "ui.html", "filename debe ser ui.html"
        assert "src" in tools[0]["content"], "El HTML debe contener src"
        print("[OK] test_html_con_src_no_rompe_parser: PASADO")
    except KeyError as e:
        print(f"[FAIL] KeyError no manejado: {e}")
        sys.exit(1)

def test_json_sin_action_no_rompe_parser():
    """Un JSON valido pero sin 'action' reconocida no debe añadir tools ni crashear."""
    respuesta_llm = (
        "```json\n"
        '{"src": "algo", "href": "otro"}\n'
        "```"
    )
    try:
        clean, tools = parse_tool_calls(respuesta_llm)
        assert len(tools) == 0, f"No deberia haber tools, encontre {len(tools)}"
        print("[OK] test_json_sin_action_no_rompe_parser: PASADO")
    except KeyError as e:
        print(f"[FAIL] KeyError no manejado: {e}")
        sys.exit(1)

def test_raw_json_con_texto_alrededor():
    """Verifica que el fallback detecta JSON crudo incluso con texto antes y después."""
    respuesta_llm = (
        "Claro, aquí tienes el archivo:\n"
        '{"action": "create_file", "filename": "app.py", "content": "print(\'hola\')"}\n'
        "Espero que te sirva."
    )
    clean, tools = parse_tool_calls(respuesta_llm)
    assert len(tools) == 1, "Debería haber detectado 1 tool en el JSON crudo"
    assert tools[0]["filename"] == "app.py"
    assert "🛠️ **Herramienta Ejecutada:**" in clean
    print("[OK] test_raw_json_con_texto_alrededor: PASADO")

def test_json_con_comillas_internas_no_escapadas():
    """
    Verifica que el extractor manual captura el contenido incluso si el LLM
    mete comillas dobles sin escapar dentro del HTML.
    """
    respuesta_llm = (
        '{"action": "create_file", "filename": "ui.html", '
        '"content": "<html><div class="test">Texto</div></html>" }'
    )
    clean, tools = parse_tool_calls(respuesta_llm)
    assert len(tools) == 1, "Debería haber detectado la tool a pesar de las comillas internas"
    assert 'class="test"' in tools[0]["content"]
    print("[OK] test_json_con_comillas_internas_no_escapadas: PASADO")

def test_respuesta_vacia_no_rompe():
    """Una respuesta sin bloques JSON debe devolver texto limpio y lista vacia."""
    respuesta_llm = "Hola! Soy el SuperAgente, encantado de ayudarte."
    clean, tools = parse_tool_calls(respuesta_llm)
    assert tools == [], "No debe haber tools en respuesta conversacional"
    assert clean == respuesta_llm, "El texto debe quedar intacto"
    print("[OK] test_respuesta_vacia_no_rompe: PASADO")

if __name__ == "__main__":
    print("\n=== TEST SUITE: agent_tools parser fix ===\n")
    test_html_con_src_no_rompe_parser()
    test_json_sin_action_no_rompe_parser()
    test_raw_json_con_texto_alrededor()
    test_json_con_comillas_internas_no_escapadas()
    test_respuesta_vacia_no_rompe()
    print("\n=== TODOS LOS TESTS PASADOS ===\n")
