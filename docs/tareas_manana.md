# Tareas Para Manana

Fecha de preparacion: 2026-05-13  
Actualizado: 2026-05-14 (sesion en curso)

## Hecho (2026-05-14)

1. ~~Separar tema UI de `config.py`~~ → `src/ui/theme.py` (`Colors`, `Spacing`, `ESTILOS_CSS`); `app.py` importa desde ahi; `config.py` solo constantes y APIs.
2. ~~Imports hacia `system_prompts`~~ → sin re-exports de prompts en `config.py`; doc `prompt_manager` alineado.
3. ~~Cobertura y subconjuntos~~ → `pytest.ini` sin `--cov-fail-under`; CI aplica `--cov-fail-under=100` en el job de unit tests.
4. Documentacion local → `docs/LOCAL_DEPLOY.md`.
5. Auditorias de planificacion → `docs/audit_runtime_chat.md`, `docs/audit_database.md`.

## Pendiente / siguiente oleada

- Ejecutar bateria completa de tests local + revisar cobertura si se amplian paquetes `--cov=`.
- Limpieza fina de artefactos Windows / duplicados de rutas en git (revisar `git status`).
- Commits logicos por bloques (`git diff` grande acumulado).
- Implementar division real de `runtime.py` / `database.py` segun los docs de auditoria.
- `docker compose down` + `up -d --build` en tu maquina y revisar logs (Grafana, worker).
