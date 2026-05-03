import subprocess
import sys

class CodeExecutionService:
    """Servicio de ejecución aislada de código Python en un Sandbox local."""
    
    def execute_python(self, code: str) -> str:
        """
        Ejecuta código Python usando subprocess.run con un timeout de 30 segundos.
        Captura stdout y stderr.
        """
        try:
            # Se usa el ejecutable actual de Python para garantizar compatibilidad
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
            return "❌ Error: La ejecución del código superó el tiempo máximo permitido de 30 segundos (Timeout)."
        except Exception as e:
            return f"❌ Error interno al intentar ejecutar el código: {str(e)}"
