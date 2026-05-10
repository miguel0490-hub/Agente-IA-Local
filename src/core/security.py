import time
from typing import Dict

# Almacén en memoria para el MVP (se migrará a Redis en el futuro)
_RATE_LIMITS: Dict[str, list] = {}

def check_rate_limit(user_id: str, limit: int = 15, window_seconds: int = 60) -> bool:
    """
    Valida si un usuario puede emitir una nueva petición.

    Args:
        user_id: Identificador único del usuario.
        limit: Número máximo de solicitudes permitidas en la ventana.
        window_seconds: Duración de la ventana deslizante en segundos.

    Returns:
        bool: ``True`` cuando la petición está permitida, ``False`` cuando se excede el límite.
    """
    now = time.time()
    user_key = str(user_id)
    
    if user_key not in _RATE_LIMITS:
        _RATE_LIMITS[user_key] = []
    
    # Limpiar timestamps viejos
    _RATE_LIMITS[user_key] = [t for t in _RATE_LIMITS[user_key] if now - t < window_seconds]
    
    if len(_RATE_LIMITS[user_key]) >= limit:
        return False # Límite excedido
        
    _RATE_LIMITS[user_key].append(now)
    return True
