class CodeExecutionService:
    """Servicio de ejecución de código Python."""

    def execute_python(self, code: str) -> str:
        """Ejecuta código Python dentro del sandbox Docker endurecido."""
        from src.services.execution_sandbox import CodeSecurityError, run_python_in_docker

        try:
            result = run_python_in_docker(code, timeout_seconds=8)
        except CodeSecurityError as exc:
            return f"⛔ Código bloqueado por política de seguridad: {exc}"

        if not result.ok:
            return f"⛔ Sandbox rechazó la ejecución: {result.error}"

        response_parts = []
        if result.stdout:
            response_parts.append(f"[STDOUT]\n{result.stdout}")
        if result.stderr:
            response_parts.append(f"[STDERR]\n{result.stderr}")
        if not response_parts:
            return "✅ Ejecución completada sin salida."
        return "\n\n".join(response_parts)
