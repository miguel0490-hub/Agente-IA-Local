# Few-Shot: Code Review

## Ejemplo 1
**Usuario:** Revisa este código Python:
```python
def get_user(id):
    conn = sqlite3.connect("db.sqlite")
    cursor = conn.execute(f"SELECT * FROM users WHERE id = {id}")
    return cursor.fetchone()
```

**Asistente:**
### 🔍 Revisión de Código

**Severidad: CRÍTICA**

1. **SQL Injection** (Crítico): Usas f-string para construir la query. Un atacante podría inyectar SQL arbitrario.
   ```python
   cursor = conn.execute("SELECT * FROM users WHERE id = ?", (id,))
   ```

2. **Resource Leak** (Alto): La conexión nunca se cierra. Usa context manager:
   ```python
   with sqlite3.connect("db.sqlite") as conn:
       cursor = conn.execute(...)
   ```

3. **Naming** (Bajo): `id` es un builtin de Python. Usa `user_id`.

## Ejemplo 2
**Usuario:** Analiza esta función de autenticación.

**Asistente:** Antes de analizar, necesito ver el código. ¿Puedes compartirlo o subir el archivo?
