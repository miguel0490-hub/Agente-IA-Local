import time
from typing import Dict

# Almacén en memoria para el MVP (se migrará a Redis en el futuro)
_RATE_LIMITS: Dict[str, list] = {}

def check_rate_limit(user_id: str, limit: int = 15, window_seconds: int = 60) -> bool:
    """
    Limita las peticiones (Sliding Window).
    Por defecto: 15 peticiones por minuto por usuario.
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
