import pandas as pd
from pypdf import PdfReader
from docx import Document
from pptx import Presentation
from odf.opendocument import load as odf_load
from odf.teletype import extractText as odf_extract_text

def _parse_pdf(file_obj) -> str:
    reader = PdfReader(file_obj)
    return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])

def _parse_docx(file_obj) -> str:
    doc = Document(file_obj)
    return "\n".join([para.text for para in doc.paragraphs])

def _parse_odf(file_obj) -> str:
    doc = odf_load(file_obj)
    return odf_extract_text(doc)

def _parse_excel(file_obj, is_ods=False) -> str:
    motor = 'odf' if is_ods else None
    df = pd.read_excel(file_obj, engine=motor)
    return f"Datos de la hoja de cálculo:\n{df.to_string()}"

def _parse_csv(file_obj) -> str:
    df = pd.read_csv(file_obj)
    return f"Datos del CSV:\n{df.to_string()}"

def _parse_pptx(file_obj) -> str:
    prs = Presentation(file_obj)
    texto = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                texto.append(shape.text)
    return "\n".join(texto)

def _parse_text(file_obj) -> str:
    return file_obj.read().decode("utf-8")

# Diccionario de estrategias
_EXTRACTORS = {
    '.pdf': _parse_pdf,
    '.docx': _parse_docx,
    '.odt': _parse_odf,
    '.odp': _parse_odf,
    '.xlsx': _parse_excel,
    '.xls': _parse_excel,
    '.ods': lambda f: _parse_excel(f, is_ods=True),
    '.csv': _parse_csv,
    '.pptx': _parse_pptx,
    '.txt': _parse_text,
    '.py': _parse_text,
    '.js': _parse_text,
    '.html': _parse_text,
    '.css': _parse_text,
    '.env': _parse_text
}

def extraer_texto_archivo(file_obj) -> str:
    """Extrae texto de un archivo basándose en su extensión mediante el patrón Strategy."""
    nombre = file_obj.name.lower()
    
    # Extraer la extensión
    extension = None
    for ext in _EXTRACTORS.keys():
        if nombre.endswith(ext):
            extension = ext
            break
            
    if not extension:
        return None
        
    try:
        extractor = _EXTRACTORS[extension]
        return extractor(file_obj)
    except Exception as e:
        return f"Error procesando {nombre}: {e}"
