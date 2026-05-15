# Few-Shot: App web HTML + CSS + JS (bundle enlazado)

## Reglas obligatorias
- Tres archivos: `index.html`, `style.css`, `app.js` (nombres exactos).
- Enlaces: `href="style.css"` y `src="app.js"` (mismos nombres que `filename` en cada `create_file`).
- Botón: `type="button"` + `preventDefault` en el click.
- Tres bloques ```json en una sola respuesta (orden: css → js → html).

## Persistencia sin backend
Usuario pide “SQL” → usar `localStorage` y comentar en texto: no hay servidor; datos en el navegador.

```javascript
const STORAGE_KEY = 'superagente_dni_validos';
const loadHistory = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    localStorage.removeItem(STORAGE_KEY);
    return [];
  }
};
```

## Tema SuperAgente (fragmento CSS)
```css
:root {
  --sa-bg: #0B0C10;
  --sa-surface: #1E293B;
  --sa-primary: #00F2FE;
  --sa-text: #FFFFFF;
  --sa-text-muted: #94A3B8;
  --sa-success: #22c55e;
  --sa-error: #ef4444;
}
body { background: var(--sa-bg); color: var(--sa-text); font-family: system-ui, sans-serif; }
button.primary { background: linear-gradient(90deg, #00F2FE, #4FACFE); color: #0B0C10; }
```

## DNI — lógica de referencia

Tabla: `TRWAGMYFPDXBNJZSQVHLCKE` · índice = `parseInt(8dígitos, 10) % 23`

```javascript
const DNI_LETTERS = 'TRWAGMYFPDXBNJZSQVHLCKE';
const letterFromDigits = (eight) => DNI_LETTERS[parseInt(eight, 10) % 23];

// 8 dígitos → calcular
if (/^\d{8}$/.test(value)) {
  const letter = letterFromDigits(value);
  showSuccess(`DNI completo: ${value}${letter}`);
}
// 8 dígitos + letra → validar
if (/^\d{8}[A-Z]$/.test(value)) {
  const nums = value.slice(0, 8);
  const expected = letterFromDigits(nums);
  if (value[8] === expected) showSuccess('DNI válido.');
  else showError(`DNI no válido. La letra correcta es ${expected} (${nums}${expected}).`);
}
```

## NIE — lógica de referencia (opcional)

```javascript
const NIE_PREFIX = { X: '0', Y: '1', Z: '2' };
const parseNie = (raw) => {
  const v = raw.trim().toUpperCase().replace(/\s/g, '');
  const m = v.match(/^([XYZ])(\d{7})([A-Z])?$/);
  if (!m) return null;
  const eight = NIE_PREFIX[m[1]] + m[2];
  return { eight, letter: m[3] || null, type: 'NIE' };
};
// Misma tabla % 23 sobre `eight`
```

## index.html (fragmento)
```html
<link rel="stylesheet" href="style.css">
<div class="container">
  <input id="dniInput" maxlength="9" autocomplete="off" />
  <button type="button" id="validateBtn" class="primary">Validar / Calcular</button>
  <div id="result" aria-live="polite"></div>
</div>
<script src="app.js" defer></script>
```
