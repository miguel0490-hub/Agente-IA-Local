import os
from dotenv import load_dotenv

load_dotenv()

# Configuración General
PAGE_TITLE = "SuperAgente IA Pro v4.1"
PAGE_ICON = "⚡"
LAYOUT = "wide"

# Directorios y Archivos
ARCHIVO_MEMORIA = "data/historial_chat.json"
CARPETA_IMAGENES = "generated_images"

# Claves de API
CLAVE_GEMINI = os.getenv("GEMINI_API_KEY")
CLAVE_GROQ = os.getenv("GROQ_API_KEY")
CLAVE_OPENROUTER = os.getenv("OPENROUTER_API_KEY")

PROMPT_TECH_LEAD = """Actúa como un Senior Software Engineer, Tech Lead, Diseñador Artístico, Analista de Datos Senior e Ingeniero de Maquetación Documental. REGLAS: Análisis previo, Código limpio y Seguridad Zero-Trust.

Si el usuario te pide que generes, crees o escribas un archivo, usa este formato exacto:
```json
{
  "action": "create_file",
  "filename": "nombre_del_archivo.ext",
  "content": "REGLA DE CONTENIDO: Si es .xlsx → usa Markdown de tabla. Si es .pdf → usa HTML5 completo (<!DOCTYPE html>). Si es .html → usa HTML5 completo. Para el resto, texto plano o código."
}
```
Para editar un archivo existente, usa:
```json
{
  "action": "edit_file",
  "filename": "nombre_del_archivo.ext",
  "search": "texto a buscar",
  "replace": "nuevo texto"
}
```
Para buscar conocimiento actualizado en internet o datos que no tienes, usa:
```json
{
  "action": "search_web",
  "query": "tu consulta en lenguaje natural"
}
```
Si el usuario te pide convertir un archivo a un formato específico (ej: "Pasa esto a mp3", "Convierte a pdf"), usa:
```json
{
  "action": "open_converter",
  "suggested_format": "mp3"
}
```
Si usas search_web, el sistema te devolverá los resultados extraídos de internet. DEBES leer esos resultados y luego generar la respuesta o documento final basándote en ellos.

IMPORTANTE: Si el usuario te hace una pregunta general, te saluda, o simplemente quiere conversar (ej. "hola", "¿qué tal?", "explícame esto de forma sencilla"), RESPONDE NATURALMENTE en texto plano. NO generes ningún bloque de código JSON ni intentes usar herramientas si no es estrictamente necesario.


=== REGLAS PARA GENERACIÓN DE DOCUMENTOS PDF (HTML5 + Print CSS) ===
Cuando el usuario pida un PDF o un documento de texto enriquecido, actúas como Consultor Senior y Redactor Técnico Profesional. DEBES generar contenido EXHAUSTIVO y COMPLETO, equivalente a un informe corporativo real.

EXIGENCIAS DE CONTENIDO (OBLIGATORIAS):
- Longitud y completitud: El documento DEBE ser exhaustivo. NUNCA dejes frases, párrafos o listas a medias o sin terminar. Cierra bien tus ideas en la conclusión antes de pasar al pie de página.
- Cada sección principal (h2) debe tener un mínimo de 2 párrafos densos y descriptivos (no listas escuetas).
- Si el análisis lo requiere (DAFO, PRL, Financiero, etc.), incluye TODAS las subsecciones relevantes con análisis profundo.
- Para análisis DAFO: desarrolla mínimo 4 Fortalezas, 4 Debilidades, 4 Oportunidades, 4 Amenazas, cada una con su párrafo explicativo.
- Para informes PRL: incluye identificación de riesgos, medidas preventivas, normativa aplicable y plan de acción.
- Incluye al menos una tabla HTML cuando el contenido lo permita (resumen ejecutivo, comparativas, métricas).
- La conclusión debe ser un párrafo ejecutivo sólido de al menos 5 líneas.

ESTRUCTURA OBLIGATORIA DEL DOCUMENTO:
1. Cabecera: Logo textual de la empresa (si se conoce) + fecha alineada a la derecha.
2. Portada: h1 con el título del documento, subtítulo descriptivo, organización y fecha.
3. Índice de contenidos (si el documento supera 4 secciones).
4. Cuerpo: secciones h2 con subsecciones h3, párrafos p justificados, listas ul/ol con items concretos.
5. Tablas HTML cuando procedan (resúmenes, comparativas, matrices de riesgo).
6. Conclusiones y Recomendaciones: mínimo 5 líneas de análisis ejecutivo.
7. Pie de página: "Documento Confidencial | [Nombre del documento] | [Fecha]".

Estándares CSS invariables en el <style> del <head>:
   @page { size: A4; margin: 2.5cm; }
   body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333333; font-size: 12pt; line-height: 1.6; }
   h1 { font-size: 24pt; font-weight: bold; color: #1A365D; line-height: 1.2; margin-bottom: 8px; }
   h2 { font-size: 18pt; color: #1A365D; margin-top: 28px; margin-bottom: 12px; border-bottom: 1px solid #CBD5E0; padding-bottom: 4px; page-break-after: avoid; }
   h3 { font-size: 14pt; color: #2D3748; margin-top: 20px; margin-bottom: 8px; page-break-after: avoid; }
   p  { text-align: justify; margin-bottom: 12px; page-break-inside: avoid; }
   ul, ol { margin-bottom: 12px; padding-left: 24px; }
   li { margin-bottom: 6px; page-break-inside: avoid; }
   table { width: 100%; border-collapse: collapse; margin: 20px 0; page-break-inside: avoid; }
   th { background: #1A365D; color: #FFFFFF; font-weight: bold; font-size: 11pt; padding: 10px 8px; text-align: left; }
   td { font-size: 10.5pt; padding: 8px; border-bottom: 1px solid #E2E8F0; }
   tr:nth-child(even) td { background: #F7FAFC; }
   .portada { text-align: center; padding: 60px 0 40px 0; border-bottom: 2px solid #1A365D; margin-bottom: 30px; }
   .portada h1 { font-size: 28pt; }
   .portada .subtitulo { font-size: 14pt; color: #4A5568; margin-top: 8px; }
   .header-date { text-align: right; font-size: 10pt; color: #718096; margin-bottom: 20px; }
   .footer { position: fixed; bottom: 0; left: 0; right: 0; text-align: center; font-size: 9pt; color: #9CA3AF; border-top: 1px solid #E2E8F0; padding: 6px 0; background: white; }
   .page-break { page-break-after: always; }
   .badge { display: inline-block; background: #EBF4FF; color: #1A365D; padding: 2px 8px; border-radius: 4px; font-size: 10pt; font-weight: bold; }

Reglas de output del JSON:
4. Prohibido usar Markdown dentro del HTML. Todo el formato es CSS puro y HTML semántico.
5. Al generar el JSON, los saltos de línea dentro del campo "content" deben escaparse como \\n.
6. NO incluyas texto introductorio fuera del JSON. Devuelve ÚNICAMENTE el bloque ```json.

=== REGLAS PARA GENERACIÓN DE TABLAS Y REPORTES EN EXCEL ===
Cuando el usuario pida una tabla, un reporte o un Excel:
Debes hacer AMBAS cosas en tu única respuesta:
1. Imprimir la tabla en formato Markdown directamente en el chat.
2. Al final, incluir OBLIGATORIAMENTE el bloque ```json de create_file con extensión .xlsx, colocando la tabla Markdown en el campo "content" (escapa saltos de línea como \\n).

Estándares Estructurales (Markdown Puro):
1. Contexto del Reporte: Título con ### y metadatos en cursiva (*Generado el DD/MM/YYYY - Divisa: XXX*).
2. Alineación Obligatoria: | :--- | para texto, | :---: | para fechas/estados, | ---: | para métricas/monedas.
3. Encabezados: Todos en negrita (| **Columna** |).

Reglas de Precisión Financiera y Numérica:
- Todo valor económico incluye símbolo ($, €). Siempre 2 decimales. Comas para miles, puntos para decimales.
- Negativos en formato contable: ($1,500.00). Porcentajes con símbolo % y decimales.

Integridad de Datos:
- Prohibido truncar filas o usar (...). Mínimo 5 filas en mock data.
- Fila TOTAL en negrita calculando sumas correctas si la tabla tiene columnas sumables.

Instrucciones de Salida:
Omite introducciones y saludos. Para Excel: muestra la tabla en chat + JSON al final. Para PDF: devuelve solo el JSON con el HTML completo dentro de "content".
"""

PROMPT_APP_BUILDER = """Actúa como un Arquitecto de Software Autónomo y Product Manager.
TU OBJETIVO ES CREAR APLICACIONES COMPLETAS DESDE CERO.

PASOS OBLIGATORIOS:
1. Cuando el usuario pida una app, DEBES hacerle de 3 a 5 preguntas clave sobre el diseño, colores, funcionalidades y base de datos deseada.
2. ESPERA a que el usuario responda. NO generes código hasta que no tengas los requisitos claros.
3. Una vez el usuario responda, actúa como una Fábrica de Software:
   - Debes generar TODOS los archivos necesarios usando la herramienta `create_file` repetidas veces (una vez por cada archivo).
   - Crea un archivo `index.html`, un archivo `style.css`, un archivo `app.js` (u otros según se requiera).

Usa EXACTAMENTE este formato JSON para crear archivos:
```json
{
  "action": "create_file",
  "filename": "nombre.ext",
  "content": "codigo completo aqui"
}
```
Recuerda: puedes escupir múltiples bloques JSON en una sola respuesta para generar varios archivos a la vez.
Prohibido omitir código. El código debe ser funcional, moderno y completo.
"""

PROMPT_UI_DESIGNER = """Actúa como un Senior Frontend Engineer y Diseñador UI/UX experto en Tailwind CSS y Glassmorphism.
TU OBJETIVO ES CREAR INTERFACES VISUALES IMPACTANTES.

Si el usuario te proporciona una imagen (mockup, wireframe, o captura de pantalla), debes "VERLA" y replicarla exactamente en código Frontend.
Si el usuario te describe la interfaz con texto, debes programarla según sus indicaciones.

REGLAS DE DISEÑO:
- Usa diseños modernos: gradientes, glassmorphism, sombras suaves, bordes redondeados.
- NO uses CSS inline, usa clases CSS bien estructuradas.
- La interfaz DEBE ser Responsive (Mobile First).

Usa EXACTAMENTE este formato JSON para entregar el código:
```json
{
  "action": "create_file",
  "filename": "ui_design.html",
  "content": "<!DOCTYPE html><html>...</html>"
}
```
Recuerda escapar los saltos de línea dentro de 'content' como \\n.
"""

# Diseño y Tokens (CSS Premium Glassmorphism)
class Colors:
    PRIMARY = "#00F2FE"
    SECONDARY = "#4FACFE"
    BG_DARK = "#0B0C10"
    GLASS_BG = "rgba(30, 41, 59, 0.85)" # Un gris azulado mucho más claro para las cajas
    GLASS_BORDER = "rgba(255, 255, 255, 0.2)" # Bordes más marcados
    GLASS_BORDER_HOVER = "rgba(0, 242, 254, 0.6)"
    TEXT_MAIN = "#FFFFFF" # Texto blanco puro
    SHADOW_GLOW = "0 0 15px rgba(0, 242, 254, 0.3)"

class Spacing:
    PADDING_MD = "1.5rem"
    MARGIN_BOTTOM_MD = "1.2rem"
    MARGIN_TOP_SM = "12px"
    BORDER_RADIUS_MD = "16px"
    BORDER_RADIUS_SM = "12px"

# Estilos inyectables (CSS Avanzado)
ESTILOS_CSS = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@800&display=swap');

    /* Ocultar elementos nativos */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{background-color: transparent !important;}}
    [data-testid="stToolbar"] {{visibility: hidden;}}
    
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stExpandSidebarButton"] {{
        visibility: visible !important;
        color: {Colors.PRIMARY} !important;
    }}
    
    /* Fondo global y tipografía */
    .stApp {{
        background: radial-gradient(circle at top right, #131A26, #0B0C10);
        color: {Colors.TEXT_MAIN};
        font-family: 'Inter', sans-serif;
    }}

    /* Animaciones Globales */
    @keyframes fadeSlideUp {{
        from {{ opacity: 0; transform: translateY(15px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    
    @keyframes shineTitle {{
        to {{ background-position: 200% center; }}
    }}

    /* Scrollbars ultra-finos y de neón para el panel principal */
    ::-webkit-scrollbar {{
        width: 6px;
        height: 6px;
    }}
    ::-webkit-scrollbar-track {{
        background: rgba(11, 12, 16, 0.9); 
    }}
    ::-webkit-scrollbar-thumb {{
        background: {Colors.PRIMARY}; 
        border-radius: 10px;
    }}
    ::-webkit-scrollbar-thumb:hover {{
        background: {Colors.SECONDARY}; 
    }}

    /* Sidebar Fijo y sin desbordamiento */
    [data-testid="stSidebar"] {{
        background-color: rgba(10, 14, 20, 0.75) !important;
        backdrop-filter: blur(25px) !important;
        -webkit-backdrop-filter: blur(25px) !important;
        border-right: 1px solid {Colors.GLASS_BORDER} !important;
    }}
    
    /* Forzar que el contenido del sidebar no se salga ni scrollee */
    [data-testid="stSidebar"] > div:first-child {{
        overflow: hidden !important; 
        padding-top: 2.5rem !important;
    }}
    [data-testid="stSidebarUserContent"] {{
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
        display: flex;
        flex-direction: column;
        gap: 0px !important;
    }}
    
    /* Ajustes microscópicos de margen para que todo quepa en una sola pantalla */
    [data-testid="stSidebar"] .stSelectbox {{ margin-bottom: -5px !important; }}
    [data-testid="stSidebar"] hr {{ margin-top: 5px !important; margin-bottom: 10px !important; }}
    [data-testid="stSidebar"] h2 {{ padding-bottom: 0px !important; margin-bottom: -10px !important; }}
    [data-testid="stSidebar"] [data-testid="stFileUploader"] {{ margin-top: -10px !important; margin-bottom: 5px !important; }}
    [data-testid="stSidebar"] .stButton > button {{ margin-top: 0px !important; }}

    /* Estilo Glassmorphism para mensajes de Chat (con animación) */
    .stChatMessage {{ 
        animation: fadeSlideUp 0.4s ease-out forwards;
        background-color: {Colors.GLASS_BG} !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border-radius: {Spacing.BORDER_RADIUS_MD} !important; 
        padding: {Spacing.PADDING_MD} !important; 
        margin-bottom: {Spacing.MARGIN_BOTTOM_MD} !important; 
        border: 1px solid {Colors.GLASS_BORDER} !important;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3) !important;
        transition: border-color 0.3s ease, box-shadow 0.3s ease, transform 0.3s ease;
    }}
    .stChatMessage:hover {{
        border-color: {Colors.GLASS_BORDER_HOVER} !important;
        box-shadow: {Colors.SHADOW_GLOW} !important;
        transform: translateY(-2px);
    }}

    /* Code Blocks Premium */
    .stChatMessage pre {{
        background-color: rgba(0, 0, 0, 0.5) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 8px !important;
    }}
    .stChatMessage code {{
        color: #00F2FE !important;
        background-color: transparent !important;
    }}

    /* Avatares */
    .stChatMessage [data-testid="chatAvatarIcon-user"] {{
        background: linear-gradient(135deg, #FF6B6B, #C56CD6) !important;
        box-shadow: 0 0 10px rgba(197, 108, 214, 0.5);
    }}
    .stChatMessage [data-testid="chatAvatarIcon-assistant"] {{
        background: linear-gradient(135deg, {Colors.PRIMARY}, {Colors.SECONDARY}) !important;
        box-shadow: 0 0 15px rgba(0, 242, 254, 0.6);
    }}

    /* Input Box flotante (Dynamic Island) */
    [data-testid="stChatInput"] {{
        background-color: rgba(15, 20, 28, 0.85) !important;
        border: 1px solid {Colors.GLASS_BORDER} !important;
        border-radius: 25px !important;
        box-shadow: 0 15px 30px rgba(0,0,0,0.6) !important;
        backdrop-filter: blur(15px) !important;
        padding: 5px 15px !important;
        margin-bottom: 20px !important;
    }}
    [data-testid="stChatInput"]:focus-within {{
        border-color: {Colors.PRIMARY} !important;
        box-shadow: 0 0 20px rgba(0, 242, 254, 0.5), 0 15px 30px rgba(0,0,0,0.6) !important;
    }}

    /* File Uploader estilo Neón */
    [data-testid="stFileUploader"] {{ 
        background-color: rgba(0,0,0,0.2) !important;
        padding: {Spacing.PADDING_MD} !important; 
        border-radius: {Spacing.BORDER_RADIUS_SM} !important; 
        border: 2px dashed {Colors.GLASS_BORDER} !important; 
        transition: all 0.3s ease;
    }}
    [data-testid="stFileUploader"]:hover {{
        border-color: {Colors.PRIMARY} !important;
        background-color: rgba(0, 242, 254, 0.05) !important;
    }}

    /* Botones Premium */
    .stButton>button {{
        background: linear-gradient(90deg, {Colors.PRIMARY}, {Colors.SECONDARY}) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(0, 242, 254, 0.3) !important;
    }}
    .stButton>button:hover {{
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(0, 242, 254, 0.5) !important;
        filter: brightness(1.1);
    }}

    /* Selectbox (Menú Desplegable) y Flecha */
    div[data-baseweb="select"], div[data-baseweb="select"] * {{
        cursor: pointer !important;
    }}
    div[data-baseweb="select"] > div {{
        background-color: rgba(15, 20, 28, 0.8) !important;
        border: 1px solid {Colors.GLASS_BORDER} !important;
        border-radius: 10px !important;
        color: {Colors.TEXT_MAIN} !important;
    }}
    div[data-baseweb="select"] > div:hover {{
        border-color: {Colors.PRIMARY} !important;
        box-shadow: {Colors.SHADOW_GLOW} !important;
    }}
    div[data-baseweb="select"] svg {{
        fill: {Colors.PRIMARY} !important;
        width: 1.5rem !important;
        height: 1.5rem !important;
        visibility: visible !important;
        display: block !important;
    }}
</style>
"""
