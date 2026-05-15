# Few-Shot: Réplica visual desde captura (HTML + CSS + JS)

## Qué copiar y qué ignorar en una captura

| Incluir (app web) | Ignorar (entorno) |
|-------------------|-------------------|
| Header, sidebar, chat, chips, avatar PRO | Barra de tareas Windows/macOS |
| Ubicación en pie del sidebar **de la web** | Clima/hora del sistema operativo |
| Logo y controles del producto | Pestañas y barra de direcciones del navegador |

## Análisis por zonas (ej. asistente tipo Gemini)

| Zona | Elementos |
|------|-----------|
| Header main | **Hamburguesa (móvil)**, marca/logo, PRO, avatar |
| Sidebar | Búsqueda, **Nueva conversación (+)**, Mis cosas, Gems, historial, Actividad, Ajustes, ubicación app |
| Hero | Saludo, titular con **gradiente** (`clamp` en móvil) |
| Input | Textarea, +, Herramientas, Pro ▼, micrófono |
| Chips | Píldoras de sugerencias |

## Layout móvil correcto

```html
<!-- El toggle VA en el header principal, no dentro del aside oculto -->
<header class='main-header'>
  <button type='button' id='menu-open' aria-label='Abrir menú'>☰</button>
  <div class='brand'>Gemini</div>
</header>
<aside class='sidebar' id='sidebar'>...</aside>
<div class='backdrop' id='backdrop' hidden></div>
```

```css
@media (max-width: 1023px) {
  .sidebar { position: fixed; transform: translateX(-100%); z-index: 40; }
  .sidebar.is-open { transform: translateX(0); }
  .backdrop.is-visible { position: fixed; inset: 0; background: rgba(0,0,0,.5); z-index: 30; }
}
/* Escritorio: SOLO grid O SOLO margin-left, nunca ambos duplicados */
@media (min-width: 1024px) {
  body { display: grid; grid-template-columns: 16rem 1fr; }
  .main-content { margin-left: 0; }
  .sidebar { position: static; transform: none; }
}
```

## app.js (referencia)

```javascript
const sidebar = document.getElementById('sidebar');
const openBtn = document.getElementById('menu-open');
const backdrop = document.getElementById('backdrop');

openBtn?.addEventListener('click', () => {
  sidebar?.classList.add('is-open');
  backdrop?.hidden = false;
});
backdrop?.addEventListener('click', () => {
  sidebar?.classList.remove('is-open');
  backdrop.hidden = true;
});
document.addEventListener('click', (e) => {
  if (!sidebar?.classList.contains('is-open')) return;
  if (sidebar.contains(e.target) || openBtn?.contains(e.target)) return;
  sidebar.classList.remove('is-open');
  if (backdrop) backdrop.hidden = true;
});

const form = document.querySelector('.input-area');
form?.addEventListener('submit', (e) => e.preventDefault());
document.querySelectorAll('.input-area button, .chip').forEach((btn) => {
  btn.setAttribute('type', 'button');
});
```

## Errores frecuentes (NO hacer)

- `#mobile-menu-toggle` **dentro** del `<aside>` que está en `translateX(-100%)` → menú inaccesible en móvil.
- `body { display: grid }` **y** `.main-content { margin-left: 260px }` a la vez en desktop.
- Icono de lápiz en “Nueva conversación” en lugar de **+**.
- Replicar clima de la barra de Windows.
- Tailwind CDN + un solo `.html`.
- `ui_design.html` enlazando a `style.css` que no existe.
