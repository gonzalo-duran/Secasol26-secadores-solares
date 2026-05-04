# Instrucciones para crear el repositorio en GitHub

Seguir estos pasos una sola vez para dejar el repo local conectado a GitHub.

---

## Paso 1 — Crear el repositorio en GitHub

1. Ir a https://github.com/new
2. Nombre del repo: `secador_solar`
3. Descripción: "Software de prediseño de secadores solares de alimentos"
4. Visibilidad: **Public**
5. **NO** inicializar con README, .gitignore ni licencia (ya los tenemos localmente)
6. Click en **Create repository**

GitHub muestra una URL del tipo:
```
https://github.com/TU_USUARIO/secador_solar.git
```
Copiar esa URL.

---

## Paso 2 — Configurar el repo local y hacer el primer commit

Abrir una terminal en el directorio raíz del proyecto (`secador_solar/`):

```bash
# Inicializar git
git init

# Agregar todos los archivos del esqueleto
git add .

# Primer commit
git commit -m "feat: esqueleto inicial del proyecto

- Estructura de carpetas definida
- Modelo de datos central completo (core/)
- Módulos de calculos/, ui/ y tests/ como esqueletos
- requirements.txt, requirements-dev.txt, pyproject.toml
- README.md con instrucciones de setup
- Licencia MIT"

# Conectar con el repo remoto (reemplazar TU_USUARIO)
git remote add origin https://github.com/TU_USUARIO/secador_solar.git

# Subir
git push -u origin main
```

---

## Paso 3 — Configurar el entorno virtual (una sola vez por máquina)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Verificar que todo instaló correctamente:
```bash
pytest tests/
```

Debe correr sin errores (3 tests pasan).

---

## Flujo normal de trabajo a partir de aquí

```bash
# Al empezar cada sesión
source .venv/bin/activate

# Al terminar de codear
black .
ruff check .
pytest
git add .
git commit -m "descripción del cambio"
git push
```
