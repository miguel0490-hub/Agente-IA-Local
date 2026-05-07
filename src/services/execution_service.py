import subprocess
import sys
import re

class CodeExecutionService:
    """Servicio de ejecución aislada de código Python en un Sandbox local."""

    # Patrones bloqueados: módulos del sistema que comprometerian el VPS host
    _DANGEROUS_PATTERNS = [
        r"import\s+os",
        r"from\s+os",
        r"import\s+sys",
        r"from\s+sys",
        r"import\s+subprocess",
        r"import\s+shutil",
        r"open\(",
        r"eval\(",
        r"exec\(",
    ]

    def execute_python(self, code: str) -> str:
        """
        Ejecuta código Python usando subprocess.run con timeout y filtro de seguridad.

        Fase 1 — Filtro Anti-RCE: bloquea módulos del sistema operativo y
        funciones de lectura/escritura de archivos antes de cualquier ejecución.
        Fase 2 — Ejecución aislada con timeout de 30 segundos.
        """
        # 1. FILTRO DE SEGURIDAD CRÍTICO (Anti-RCE para SaaS)
        for pattern in self._DANGEROUS_PATTERNS:
            if re.search(pattern, code):
                return (
                    "⛔ ALERTA DE SEGURIDAD DEL SISTEMA:\n"
                    "La ejecución de este código ha sido bloqueada. En este entorno en la nube, "
                    "no se permite el uso de módulos del sistema (os, sys, subprocess) ni lectura/escritura "
                    "directa de archivos por motivos de seguridad.\n"
                    "Por favor, limita el código a cálculos matemáticos, manipulación de datos (pandas/numpy) "
                    "o lógica algorítmica inofensiva."
                )

        # 2. EJECUCIÓN DEL CÓDIGO
        try:
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=30
            )

            output = ""
            if result.stdout:
                output += f"--- STDOUT ---\n{result.stdout}\n"
            if result.stderr:
                output += f"--- STDERR ---\n{result.stderr}\n"

            if not output.strip():
                output = "(Ejecución exitosa, sin salida en consola)"

            return output
        except subprocess.TimeoutExpired:
            return "❌ Error: La ejecución superó el tiempo máximo de 30 segundos (Timeout)."
        except Exception as e:
            return f"❌ Error interno al ejecutar el código: {str(e)}"
