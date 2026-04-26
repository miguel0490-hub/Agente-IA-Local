def parse_intent(prompt: str) -> tuple[bool, str]:
    """
    Analiza el prompt del usuario y devuelve si es un comando de imagen
    y el prompt artístico extraído.
    Retorna: (es_comando_imagen, prompt_artistico)
    """
    prompt_lower = prompt.strip().lower()
    triggers_arte = [
        "crea una imagen", "genera una imagen", "crear una imagen", 
        "generar una imagen", "dibuja una imagen", "haz una imagen"
    ]
    
    for trigger in triggers_arte:
        if trigger in prompt_lower:
            return True, prompt.strip()
            
    return False, ""
