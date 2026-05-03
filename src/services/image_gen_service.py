"""
image_gen_service.py
====================
Capa de servicios para Generación de Imágenes del Agente.

Responsabilidades:
  - Generación de imágenes con OpenAI DALL-E 3
  - Generación de imágenes con Stability AI (SDXL / Stable Image Core)

Principio de diseño:
  La función pública `generate_image` actúa como fachada (Facade Pattern).
  El caller no sabe qué proveedor se usó internamente.
  Devuelve siempre (filepath, error_message) — misma firma que GeminiProvider.generar_imagen.
"""

import os
import io
import base64
import datetime
import requests
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(override=True)

# ─── Constantes de Configuración ───────────────────────────────────────────────
_DALLE_MODEL = "dall-e-3"
_DALLE_DEFAULT_SIZE = "1024x1024"
_DALLE_DEFAULT_QUALITY = "standard"   # "standard" | "hd" — hd consume 2 créditos
_STABILITY_API_URL = "https://api.stability.ai/v2beta/stable-image/generate/core"
_STABILITY_DEFAULT_OUTPUT_FORMAT = "png"
_OUTPUT_DIR = Path("generated_images")

# Proveedores disponibles expuestos al frontend
PROVEEDORES_IMAGEN = {
    "openai_dalle3": "OpenAI DALL-E 3",
    "stability_ai": "Stability AI (Stable Image Core)",
}


def _translate_prompt_to_english(prompt: str, api_key: str) -> str:
    """
    Traduce el prompt del usuario al inglés usando Llama 3 para asegurar compatibilidad con Stability AI.
    """
    if not prompt.strip():
        return ""
    
    # Heurística rápida: si el prompt es muy corto y parece inglés, no traducir. 
    # Pero por seguridad, para Stability, mejor traducir siempre.
    try:
        from groq import Groq
        cliente = Groq(api_key=os.getenv("GROQ_API_KEY", api_key)) # Intentar usar clave de Groq
        
        system_prompt = (
            "Eres un traductor experto de prompts para generación de imágenes. "
            "Tu tarea es traducir el prompt del usuario al inglés, haciéndolo más "
            "descriptivo y técnico para modelos como Stable Diffusion. "
            "Solo devuelve la traducción en inglés, nada más."
        )
        
        response = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Traduce este prompt a inglés artístico: {prompt}"}
            ],
            temperature=0
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return prompt # Fallback al original si falla la traducción


def _require_env_key(var_name: str) -> str:
    """Valida y retorna una variable de entorno. Lanza ValueError si no existe."""
    value = os.getenv(var_name)
    if not value:
        raise ValueError(
            f"❌ Variable de entorno '{var_name}' no encontrada. "
            f"Añádela a tu archivo .env para usar esta funcionalidad."
        )
    return value


def _build_output_path(prefix: str = "dalle", extension: str = "png") -> Path:
    """Genera una ruta de archivo con timestamp para el asset generado."""
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return _OUTPUT_DIR / f"{prefix}_{timestamp}.{extension}"


# ─── Proveedor: OpenAI DALL-E 3 ────────────────────────────────────────────────

def generate_image_dalle3(
    prompt: str,
    size: str = _DALLE_DEFAULT_SIZE,
    quality: str = _DALLE_DEFAULT_QUALITY,
) -> tuple[Optional[str], Optional[str]]:
    """
    Genera una imagen con OpenAI DALL-E 3.

    Args:
        prompt: Descripción de la imagen a generar (se recomienda detallado, en inglés).
        size: Resolución. Opciones: "1024x1024", "1792x1024", "1024x1792".
        quality: "standard" (rápido) o "hd" (mayor detalle, mayor costo).

    Returns:
        Tuple (filepath, error_message).
    """
    try:
        clave_openai = _require_env_key("OPENAI_API_KEY")

        from openai import OpenAI
        cliente = OpenAI(api_key=clave_openai)

        response = cliente.images.generate(
            model=_DALLE_MODEL,
            prompt=prompt,
            size=size,
            quality=quality,
            n=1,
            response_format="b64_json"   # Base64 evita depender de URLs temporales
        )

        image_b64 = response.data[0].b64_json
        if not image_b64:
            return None, "⚠️ DALL-E 3 no devolvió imagen. El prompt pudo ser rechazado por los filtros de contenido."

        image_bytes = base64.b64decode(image_b64)
        output_path = _build_output_path(prefix="dalle3")
        output_path.write_bytes(image_bytes)

        return str(output_path), None

    except ValueError as config_error:
        return None, str(config_error)
    except Exception as api_error:
        return None, f"❌ Error en DALL-E 3: {api_error}"


# ─── Proveedor: Stability AI ───────────────────────────────────────────────────

def generate_image_stability(
    prompt: str,
    negative_prompt: str = "",
    aspect_ratio: str = "1:1",
) -> tuple[Optional[str], Optional[str]]:
    """
    Genera una imagen con Stability AI (Stable Image Core vía REST API v2beta).

    Args:
        prompt: Descripción positiva de la imagen.
        negative_prompt: Elementos a evitar en la imagen.
        aspect_ratio: Proporción. Opciones: "1:1", "16:9", "9:16", "3:2", "2:3", "4:5", "5:4".

    Returns:
        Tuple (filepath, error_message).
    """
    try:
        clave_stability = _require_env_key("STABILITY_API_KEY")
        clave_groq = os.getenv("GROQ_API_KEY")

        # [NUEVO] Traducción automática para evitar el error 422 de Stability
        prompt_en = _translate_prompt_to_english(prompt, clave_groq)

        headers = {
            "Authorization": f"Bearer {clave_stability}",
            "Accept": "image/*",
        }
        form_data = {
            "prompt": (None, prompt_en),
            "output_format": (None, _STABILITY_DEFAULT_OUTPUT_FORMAT),
            "aspect_ratio": (None, aspect_ratio),
        }
        if negative_prompt:
            form_data["negative_prompt"] = (None, negative_prompt)

        response = requests.post(
            _STABILITY_API_URL,
            headers=headers,
            files=form_data,
            timeout=60
        )

        if response.status_code == 200:
            output_path = _build_output_path(prefix="stability")
            output_path.write_bytes(response.content)
            return str(output_path), None

        # Parsear error de la API de Stability
        try:
            error_body = response.json()
            error_detail = error_body.get("errors", [str(response.text)])[0]
        except Exception:
            error_detail = response.text

        return None, f"❌ Error Stability AI ({response.status_code}): {error_detail}"

    except ValueError as config_error:
        return None, str(config_error)
    except Exception as api_error:
        return None, f"❌ Error en Stability AI: {api_error}"


# ─── Fachada Pública ───────────────────────────────────────────────────────────

def generate_image(
    prompt: str,
    provider: str = "openai_dalle3",
    **kwargs
) -> tuple[Optional[str], Optional[str]]:
    """
    Fachada unificada para generar imágenes.
    Enruta al proveedor correcto según el parámetro `provider`.

    Args:
        prompt: Descripción de la imagen.
        provider: "openai_dalle3" | "stability_ai"
        **kwargs: Argumentos específicos del proveedor (size, quality, aspect_ratio, etc.)

    Returns:
        Tuple (filepath, error_message) — idéntico a GeminiProvider.generar_imagen.
    """
    if provider == "openai_dalle3":
        return generate_image_dalle3(prompt, **kwargs)
    elif provider == "stability_ai":
        return generate_image_stability(prompt, **kwargs)
    else:
        return None, f"❌ Proveedor de imágenes desconocido: '{provider}'. Usa: {list(PROVEEDORES_IMAGEN.keys())}"
