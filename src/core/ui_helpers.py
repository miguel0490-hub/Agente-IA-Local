import streamlit as st
import os
import mimetypes

def render_download_button(filepath: str):
    """
    Renderiza un botón de descarga en Streamlit para cualquier tipo de archivo.
    Detecta automáticamente el tipo MIME basado en la extensión.
    """
    if os.path.exists(filepath):
        filename = os.path.basename(filepath)
        mime_type, _ = mimetypes.guess_type(filepath)
        
        # Fallback si no detecta el tipo
        if not mime_type:
            mime_type = "application/octet-stream"

        if "_download_button_counter" not in st.session_state:
            st.session_state._download_button_counter = 0
        st.session_state._download_button_counter += 1
        unique_key = f"download_{filename}_{st.session_state._download_button_counter}"

        with open(filepath, "rb") as file:
            st.download_button(
                label=f"⬇️ Descargar {filename}",
                data=file,
                file_name=filename,
                mime=mime_type,
                key=unique_key,
                use_container_width=True
            )
