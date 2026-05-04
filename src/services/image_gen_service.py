import os
import io
import base64
import datetime
import requests
from pathlib import Path
from typing import Optional

_DALLE_MODEL = "dall-e-3"
_DALLE_DEFAULT_SIZE = "1024x1024"
_DALLE_DEFAULT_QUALITY = "standard"   
_STABILITY_API_URL = "https://api.stability.ai/v2beta/stable-image/generate/core"
_STABILITY_DEFAULT_OUTPUT_FORMAT = "png"
_OUTPUT_DIR = Path("generated_images")

PROVEEDORES_IMAGEN = {
    "openai_dalle3": "OpenAI DALL-E 3",
    "stability_ai": "Stability AI (Stable Image Core)",
}

def _translate_prompt_to_english(prompt: str, api_key: str) -> str:
    """Traduce el prompt del usuario al inglés usando Llama 3."""
    if not prompt.strip() or not api_key:
        return prompt
    try:
        from groq import Groq
        cliente = Groq(api_key=api_key)
        
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
        return prompt 

def _build_output_path(prefix: str = "dalle", extension: str = "png") -> Path:
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return _OUTPUT_DIR / f"{prefix}_{timestamp}.{extension}"


def generate_image_dalle3(
    prompt: str,
    api_key: str,
    size: str = _DALLE_DEFAULT_SIZE,
    quality: str = _DALLE_DEFAULT_QUALITY,
) -> tuple[Optional[str], Optional[str]]:
    try:
        if not api_key:
            return None, "❌ Funcionalidad omitida durante el onboarding por falta de clave (OpenAI DALL-E 3). Por favor, actualiza tu perfil."

        from openai import OpenAI
        cliente = OpenAI(api_key=api_key)

        response = cliente.images.generate(
            model=_DALLE_MODEL,
            prompt=prompt,
            size=size,
            quality=quality,
            n=1,
            response_format="b64_json"
        )

        image_b64 = response.data[0].b64_json
        if not image_b64:
            return None, "⚠️ DALL-E 3 no devolvió imagen. El prompt pudo ser rechazado por los filtros de contenido."

        image_bytes = base64.b64decode(image_b64)
        output_path = _build_output_path(prefix="dalle3")
        output_path.write_bytes(image_bytes)

        return str(output_path), None

    except Exception as api_error:
        return None, f"❌ Error en DALL-E 3: {api_error}"


def generate_image_stability(
    prompt: str,
    api_key: str,
    groq_api_key: str = None,
    negative_prompt: str = "",
    aspect_ratio: str = "1:1",
) -> tuple[Optional[str], Optional[str]]:
    try:
        if not api_key:
            return None, "❌ Funcionalidad omitida durante el onboarding por falta de clave (Stability AI). Por favor, actualiza tu perfil."

        prompt_en = _translate_prompt_to_english(prompt, groq_api_key)

        headers = {
            "Authorization": f"Bearer {api_key}",
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

        try:
            error_body = response.json()
            error_detail = error_body.get("errors", [str(response.text)])[0]
        except Exception:
            error_detail = response.text

        return None, f"❌ Error Stability AI ({response.status_code}): {error_detail}"

    except Exception as api_error:
        return None, f"❌ Error en Stability AI: {api_error}"


def generate_image(
    prompt: str,
    provider: str = "openai_dalle3",
    api_key: str = None,
    groq_api_key: str = None,
    **kwargs
) -> tuple[Optional[str], Optional[str]]:
    if provider == "openai_dalle3":
        return generate_image_dalle3(prompt, api_key, **kwargs)
    elif provider == "stability_ai":
        return generate_image_stability(prompt, api_key, groq_api_key, **kwargs)
    else:
        return None, f"❌ Proveedor de imágenes desconocido: '{provider}'. Usa: {list(PROVEEDORES_IMAGEN.keys())}"
