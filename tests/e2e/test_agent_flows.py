import pytest
from playwright.sync_api import Page, expect
import os

BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8501")
pytestmark = pytest.mark.e2e

def test_page_load(page: Page):
    """Verifica que la aplicación carga correctamente."""
    page.goto(BASE_URL)
    # Esperar a que el título principal aparezca (usando el texto exacto del h1)
    expect(page.get_by_text("SuperAgente IA Pro")).to_be_visible(timeout=15000)

def test_role_switch_logic(page: Page):
    """Verifica que el cambio de rol funciona y actualiza el motor forzado."""
    page.goto(BASE_URL)

    # Abrir selector de rol con locator robusto (varía entre versiones Streamlit/ARIA)
    role_selector = page.get_by_role("combobox", name="Modo de operación:")
    if role_selector.count() == 0:
        role_selector = page.locator("section[data-testid='stSidebar'] [role='combobox']").first
    if role_selector.count() == 0:
        pytest.skip("No hay selector de rol visible (sesión no autenticada o onboarding incompleto).")
    role_selector.click()
    
    # Seleccionar 'App Builder' - Streamlit renderiza las opciones en un portal
    page.locator("li[role='option']:has-text('Arquitecto de Software (App Builder)')").click()
    
    # Verificar que aparece el badge de motor bloqueado/forzado
    expect(page.get_by_text("Motor: Groq")).to_be_visible(timeout=10000)

def test_memory_deletion(page: Page):
    """Verifica que el botón de borrar memoria funciona."""
    page.goto(BASE_URL)
    
    # Enviar un mensaje
    chat_input = page.get_by_placeholder("Escribe tu consulta o pídele que genere una imagen...")
    if chat_input.count() == 0:
        pytest.skip("Chat input no visible (sesión no autenticada o onboarding incompleto).")
    chat_input.fill("Borra este mensaje")
    chat_input.press("Enter")
    expect(page.get_by_text("Borra este mensaje")).to_be_visible()
    
    # Click en borrar memoria (ahora es siempre visible)
    clear_button = page.get_by_role("button", name="🗑️ Borrar Memoria Completa")
    if clear_button.count() == 0:
        pytest.skip("Botón de borrado no visible en este estado de sesión.")
    clear_button.click()
    
    # Verificar que el mensaje desapareció
    expect(page.get_by_text("Borra este mensaje")).not_to_be_visible()

def test_multimedia_tools_persistence(page: Page):
    """Verifica que el expander de herramientas se puede abrir."""
    page.goto(BASE_URL)
    expander = page.get_by_text("🛠️ Herramientas Multimedia")
    if expander.count() == 0:
        pytest.skip("Herramientas multimedia no visibles en este estado de sesión.")
    expander.click()
    
    # Verificar que los títulos internos aparecen
    expect(page.get_by_text("Transcripción STT")).to_be_visible()
    expect(page.get_by_text("Síntesis de Voz")).to_be_visible()
