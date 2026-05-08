import logging
import os

def get_logger(name: str):
    """Configura y retorna un logger estructurado."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Salida por consola
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        # Salida a archivo (Rotatorio simple)
        os.makedirs("logs", exist_ok=True)
        fh = logging.FileHandler("logs/app.log", encoding="utf-8")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
    return logger
