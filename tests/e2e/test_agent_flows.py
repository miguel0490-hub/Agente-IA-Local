import pytest
from playwright.sync_api import Page, expect
import os

BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8501")

def test_page_load(page: Page):
    """Verifica que la aplicación carga correctamente."""
    page.goto(BASE_URL)
    # Esperar a que el título principal aparezca (usando el texto exacto del h1)
    expect(page.get_by_text("SuperAgente IA Pro")).to_be_visible(timeout=15000)

def test_role_switch_logic(page: Page):
    """Verifica que el cambio de rol funciona y actualiza el motor forzado."""
    page.goto(BASE_URL)
    
    # Abrir el selector de rol
    page.get_by_label("Modo de operación:").click()
    
    # Seleccionar 'App Builder' - Streamlit renderiza las opciones en un portal
    page.locator("li[role='option']:has-text('Arquitecto de Software (App Builder)')").click()
    
    # Verificar que aparece el badge de motor bloqueado/forzado
    expect(page.get_by_text("Motor: Groq")).to_be_visible(timeout=10000)

def test_memory_deletion(page: Page):
    """Verifica que el botón de borrar memoria funciona."""
    page.goto(BASE_URL)
    
    # Enviar un mensaje
    chat_input = page.get_by_placeholder("Escribe tu consulta o pídele que genere una imagen...")
    chat_input.fill("Borra este mensaje")
    chat_input.press("Enter")
    expect(page.get_by_text("Borra este mensaje")).to_be_visible()
    
    # Click en borrar memoria (ahora es siempre visible)
    page.get_by_role("button", name="🗑️ Borrar Memoria Completa").click()
    
    # Verificar que el mensaje desapareció
    expect(page.get_by_text("Borra este mensaje")).not_to_be_visible()

def test_multimedia_tools_persistence(page: Page):
    """Verifica que el expander de herramientas se puede abrir."""
    page.goto(BASE_URL)
    expander = page.get_by_text("🛠️ Herramientas Multimedia")
    expander.click()
    
    # Verificar que los títulos internos aparecen
    expect(page.get_by_text("Transcripción STT")).to_be_visible()
    expect(page.get_by_text("Síntesis de Voz")).to_be_visible()
