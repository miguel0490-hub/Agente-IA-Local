# Auditoría: `src/database/database.py` — plan de separación

## Estado actual

- **Monolito** con motor SQLAlchemy Core (`Table`/`metadata`), `SessionLocal`, y **muchas funciones públicas** en un solo archivo (~870+ líneas).
- Dominios mezclados: **auth** (registro, login, tokens, remember-me, reset password), **perfil**, **admin** (usuarios, stats, toggles), **contacto**, **chats/mensajes**, **uso/costes**, **cifrado** (`get_cipher`, rotación de clave).

## Objetivo de arquitectura

Separar por paquete manteniendo **una API estable** durante la transición:

| Módulo sugerido | Responsabilidad |
|-----------------|-----------------|
| `src/database/engine.py` | `DATABASE_URL`, `engine`, `SessionLocal`, `metadata`, helpers `_is_postgres`, `get_connection` |
| `src/database/models.py` o `schema.py` | Definiciones `Table` |
| `src/database/users.py` | Registro, login, perfil, API keys cifradas, admin sobre usuarios |
| `src/database/auth_tokens.py` | verify/remember/reset tokens, limpieza expirados |
| `src/database/chats.py` | CRUD chats y mensajes, búsqueda |
| `src/database/contact.py` | Mensajes de contacto y stats |
| `src/database/usage.py` | `persist_usage_entry`, resúmenes |

`database.py` puede reexportar funciones (`from .users import register_user, ...`) para no romper `import src.database.database as db` de golpe.

## Orden de migración recomendado

1. Extraer **schema + engine** (cero cambio de comportamiento).
2. Mover **contact + usage** (menos acoplamiento).
3. Mover **chats/messages**.
4. Por último **users + auth_tokens** (más referencias cruzadas y tests de seguridad).

## Pruebas

- Mantener tests que usen SQLite en memoria o `data/` temporal.
- Tras cada movimiento: `pytest` sobre `tests/` que importen `database`.
