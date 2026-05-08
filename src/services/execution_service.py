class CodeExecutionService:
    """Servicio de ejecución de código Python."""

    def execute_python(self, code: str) -> str:
        """
        Bloqueo de seguridad (Fase 1).
        La ejecución local de código está deshabilitada en este entorno para prevenir RCE.
        """
        return (
            "⛔ ALERTA DE SEGURIDAD:\n"
            "La ejecución de código remota ha sido temporalmente deshabilitada en este "
            "entorno de producción por políticas de seguridad Zero-Trust.\n"
            "El sistema de Sandbox aislado mediante contenedores está en construcción."
        )
