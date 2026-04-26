"""
Test de integración completo: replica exactamente el pipeline de producción.
Ejecuta: python test_full_pipeline.py
"""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

print("=" * 60)
print("TEST 1: Verificar imports y configuración de pdfkit")
print("=" * 60)
from src.services.file_factory import FileFactory, HAS_PDFKIT, PDFKIT_CONFIG
print(f"HAS_PDFKIT  : {HAS_PDFKIT}")
print(f"PDFKIT_CONFIG wkhtmltopdf: {getattr(PDFKIT_CONFIG, 'wkhtmltopdf', 'None')}")

print("\n" + "=" * 60)
print("TEST 2: _create_pdf con HTML real (ruta absoluta)")
print("=" * 60)

HTML_REAL = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
@page { size: A4; margin: 2.5cm; }
body { font-family: Arial; color: #333333; font-size: 12pt; line-height: 1.6; }
h1 { font-size: 24pt; color: #1A365D; }
h2 { font-size: 18pt; color: #1A365D; border-bottom: 1px solid #CBD5E0; }
p { text-align: justify; margin-bottom: 12px; }
.footer { position: fixed; bottom: 0; text-align: center; font-size: 9pt; color: #9CA3AF; }
</style>
</head>
<body>
<div style="text-align:right;font-size:10pt;color:#718096;">Generado el 26/04/2026</div>
<h1>Analisis DAFO y PRL - Almacen de Bebidas Mayorista en Malaga</h1>
<h2>1. Introduccion</h2>
<p>El almacen de bebidas mayorista analizado opera en la provincia de Malaga, 
distribuyendo productos a bares, restaurantes y comercios minoristas de la zona.</p>
<h2>2. Analisis DAFO</h2>
<h3>Fortalezas</h3>
<p>La empresa cuenta con una amplia red de distribucion bien establecida y 
reconocida en el mercado local con mas de 15 anos de experiencia.</p>
<h3>Debilidades</h3>
<p>La dependencia de un numero limitado de proveedores nacionales supone 
un riesgo de desabastecimiento en situaciones de crisis de suministro.</p>
<h2>3. Plan de PRL</h2>
<p>Segun la Ley 31/1995 de Prevencion de Riesgos Laborales, la empresa debe 
implementar las medidas preventivas detalladas en este documento.</p>
<div class="footer">Documento Confidencial | Analisis DAFO PRL | 26/04/2026</div>
</body>
</html>"""

factory = FileFactory(output_dir=os.path.abspath('generated_images'))
filepath_out = os.path.abspath(os.path.join('generated_images', 'test_integration.pdf'))

result = factory._create_pdf(filepath_out, HTML_REAL)
print(f"Resultado _create_pdf: {result}")
if result:
    ext = os.path.splitext(result)[1]
    size = os.path.getsize(result) if os.path.exists(result) else 0
    print(f"Extension generada  : {ext}")
    print(f"Tamano del archivo  : {size} bytes")
    if ext == '.pdf' and size > 1024:
        print(">>> EXITO: PDF generado correctamente <<<")
    elif ext == '.html':
        print(">>> FALLO: Se genero HTML en lugar de PDF <<<")
    else:
        print(f">>> PROBLEMA: resultado inesperado <<<")
else:
    print(">>> FALLO TOTAL: resultado None <<<")

print("\n" + "=" * 60)
print("TEST 3: execute_tool completo (como lo llama agente.py)")
print("=" * 60)

tool_data = {
    "action": "create_file",
    "filename": "test_execute_tool.pdf",
    "content": HTML_REAL
}
result2 = factory.execute_tool(tool_data)
print(f"Resultado execute_tool: {result2}")
if result2:
    ext2 = os.path.splitext(result2)[1]
    size2 = os.path.getsize(result2) if os.path.exists(result2) else 0
    print(f"Extension generada  : {ext2}")
    print(f"Tamano del archivo  : {size2} bytes")
    if ext2 == '.pdf':
        print(">>> EXITO <<<")
    else:
        print(">>> FALLO: se genero", ext2, "en vez de .pdf <<<")

print("\n" + "=" * 60)
print("TEST 4: Deteccion HTML en _create_pdf")
print("=" * 60)
content_lower = HTML_REAL.lower()
is_html = (
    "<!doctype html" in content_lower
    or "<html" in content_lower
    or ("<head>" in content_lower and "<body>" in content_lower)
)
print(f"content_is_html detectado: {is_html}")
print(f"Empieza con '<!doctype': {HTML_REAL.strip().lower().startswith('<!doctype')}")
