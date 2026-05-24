# Bitácora — Sesión 33 (2026-05-23)

**Tema:** Migración de la infraestructura de deploy — de repositorio público en GitHub + Streamlit Community Cloud a repositorio privado en GitHub + Hugging Face Spaces (Docker/Streamlit), con deploy automático vía GitHub Action.

**Estado al cierre de la sesión:** App Secasol26 corriendo en Hugging Face Spaces con deploy automático desde repo privado de GitHub. Pipeline verificado: push a `main` → GitHub Action → sync a HF Space → rebuild → app actualizada. Suite de tests sin cambios (no se tocó código de `core/`, `calculos/` ni `ui/`).

---

## 131. Motivación

El usuario quería proteger el código fuente del proyecto mientras seguía compartiendo la app con compañeros de trabajo vía URL sin que necesiten instalar nada. El repo en GitHub era público (requisito de Streamlit Community Cloud en plan gratuito), lo que permitía a cualquiera forkear, clonar y ver el código.

Objetivo: código cerrado + app accesible por URL + deploy automático.

---

## 132. Análisis de opciones

Se evaluaron 4 alternativas:

| Opción | Descripción | Pros | Contras |
| :--- | :--- | :--- | :--- |
| 1 — Streamlit Cloud Teams/Enterprise | Repo privado + Streamlit Cloud pagos | Solución limpia | Costo mensual |
| 2 — Repo público con protecciones | Deshabilitar fork + licencia restrictiva | Sin costo | No impide `git clone`; protección solo legal, no técnica |
| 3 — Repo privado + deploy alternativo | HF Spaces, Railway, Render, etc. | Código realmente cerrado + app pública | Migración necesaria |
| 4 — Dos repos (privado + espejo público) | Privado para desarrollo, público solo para deploy | Control de qué se expone | Mantenimiento doble |

**Decisión:** Opción 3 — repo privado en GitHub + deploy en Hugging Face Spaces.

**Razones:** Hugging Face Spaces soporta Streamlit nativamente (vía Docker), es gratuito en tier CPU Basic (2 vCPU, 16 GB RAM), y es una plataforma familiar en la comunidad científica. Los compañeros acceden por URL sin cuenta.

---

## 133. Hallazgos durante la implementación

### 133.1 Streamlit SDK deprecado en HF Spaces

Al crear el Space, la interfaz web de Hugging Face ya no ofrece Streamlit como SDK directo. Las opciones visibles son Gradio, Docker y Static. La documentación oficial de HF confirma que el SDK nativo de Streamlit está **deprecado**. La vía recomendada es seleccionar **Docker** y luego elegir el **template de Streamlit** que aparece dentro de las opciones de Docker.

### 133.2 Archivos binarios y Git LFS

Hugging Face rechaza push de archivos binarios sin Git LFS o Xet. Los archivos afectados fueron:

- Fonts `.ttf` (DejaVu Sans, usados por el reporte PDF)
- Logos `.png` (GEEDSP, INENCO)
- Archivos `.pyc` (caché de Python, no deberían haberse subido)

**Solución:** se instaló `git-lfs` (`sudo dnf install git-lfs`), se configuró tracking para `*.ttf`, `*.png` y `*.parquet`, se limpiaron los `__pycache__/` y el caché de NASA POWER (`data/cache/`) que no son necesarios en el deploy (se regeneran en runtime).

### 133.3 Permisos de token de GitHub para workflows

El token clásico de GitHub necesita el scope `workflow` para poder crear o modificar archivos en `.github/workflows/`. Sin este permiso, `git push` rechaza el archivo del Action. Se resolvió editando el token existente en GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic) y tildando `workflow`.

### 133.4 Tokens de GitHub vs Hugging Face

Son plataformas completamente independientes. Los tokens de GitHub no aparecen en Hugging Face ni viceversa. El token de HF (tipo Write) se almacena como secreto en GitHub (`HF_TOKEN`) para que el Action pueda autenticarse.

---

## 134. Arquitectura de deploy resultante

```
Flujo de trabajo diario:

  Máquina local (VS Code / Claude Code)
       │
       │  git push (a main)
       ▼
  GitHub (repo PRIVADO: gonzalo-duran/Secasol26-secadores-solares)
       │
       │  GitHub Action (deploy_hf.yml) — se dispara automáticamente
       ▼
  Hugging Face Space (gonzalojduran/Secasol26)
       │
       │  Docker build + Streamlit run
       ▼
  App pública: https://huggingface.co/spaces/gonzalojduran/Secasol26
       │
       ▼
  Compañeros acceden por URL (sin instalar nada, sin ver código)
```

---

## 135. Estructura del Space en Hugging Face

El Space tiene su propio repo Git con la siguiente estructura:

```
Secasol26/
├── Dockerfile              ← template Docker/Streamlit de HF
├── README.md               ← metadata YAML del Space
├── .gitattributes          ← configuración de Git LFS
├── .gitignore              ← excluye __pycache__/ y data/cache/
├── requirements.txt        ← dependencias del proyecto
└── src/
    ├── Secasol.py           ← entry point de Streamlit
    ├── ui/                  ← módulos de interfaz
    ├── calculos/            ← motores de cálculo
    ├── core/                ← modelo de datos
    ├── assets/              ← logos, fonts, esquemas SVG
    ├── catalogo/            ← YAMLs de materiales y productos
    └── data/                ← directorio para caché (vacío en deploy)
```

El `Dockerfile` generado por el template:

```dockerfile
FROM python:3.13.5-slim
WORKDIR /app
RUN apt-get update && apt-get install -y \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
COPY src/ ./src/
RUN pip3 install -r requirements.txt
EXPOSE 8501
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health
ENTRYPOINT ["streamlit", "run", "src/Secasol.py", \
            "--server.port=8501", "--server.address=0.0.0.0"]
```

---

## 136. GitHub Action — deploy automático

Archivo: `.github/workflows/deploy_hf.yml`

El Action se dispara en cada push a `main` y realiza los siguientes pasos:

1. Checkout del repo de GitHub (con LFS).
2. Clona el Space de HF usando `HF_TOKEN` (secreto de GitHub).
3. Preserva los archivos propios del Space (`Dockerfile`, `README.md`, `.gitattributes`).
4. Limpia `src/` del Space y copia el código actualizado desde el repo de GitHub.
5. Restaura los archivos preservados.
6. Elimina `__pycache__/` para no subir basura.
7. Commit y push al Space solo si hay cambios.

El secreto `HF_TOKEN` se configuró en GitHub → repo → Settings → Secrets and variables → Actions.

---

## 137. Pasos ejecutados (secuencia completa)

1. Creación de cuenta en Hugging Face (usuario: `gonzalojduran`).
2. Creación del Space `Secasol26` con SDK Docker → template Streamlit.
3. Verificación de que el template de ejemplo corre (espiral de puntos).
4. Clonación del Space en la máquina local (`git clone`).
5. Copia de los archivos del proyecto al Space (`Secasol.py`, `ui/`, `calculos/`, `core/`, `assets/`, `catalogo/`, `data/`, `requirements.txt`).
6. Eliminación de la app de ejemplo (`streamlit_app.py`).
7. Modificación del `Dockerfile` para apuntar a `src/Secasol.py`.
8. Instalación de `git-lfs` y configuración de tracking para binarios.
9. Creación de `.gitignore` para excluir `__pycache__/` y `data/cache/`.
10. Commit y push al Space (con autenticación por token HF en la URL).
11. Verificación de que la app corre en HF Spaces.
12. Cambio de visibilidad del repo de GitHub a **privado** (Settings → Danger Zone → Change visibility).
13. Creación del GitHub Action (`deploy_hf.yml`).
14. Adición del scope `workflow` al token clásico de GitHub.
15. Push del Action a GitHub.
16. Verificación de que el Action se ejecutó exitosamente (tic verde, 9 segundos).
17. Revocación del token de HF expuesto accidentalmente en el chat.

---

## 138. Decisiones tomadas

- [x] **Deploy en Hugging Face Spaces** en lugar de Streamlit Community Cloud, Railway o Render.
- [x] **Docker con template Streamlit** (SDK nativo de Streamlit deprecado en HF).
- [x] **Git LFS** para archivos binarios (fonts, logos). No se usa Xet.
- [x] **Caché de NASA POWER excluido del deploy** — se regenera en runtime.
- [x] **GitHub Action para deploy automático** — no se requiere intervención manual para actualizar la app.
- [x] **Carpeta `Secasol26/` local excluida del repo de GitHub** (agregada a `.gitignore`) — ya no es necesaria con el Action.
- [x] **Repo de GitHub cambiado a privado.**

---

## 139. Archivos nuevos o modificados en el repo de GitHub

| Archivo | Acción | Descripción |
| :--- | :--- | :--- |
| `.github/workflows/deploy_hf.yml` | NUEVO | GitHub Action para deploy automático a HF Space |
| `.gitignore` | MODIFICADO | Agregado `Secasol26/` |

---

## 140. URLs de referencia

| Recurso | URL |
| :--- | :--- |
| App (para compartir con compañeros) | `https://huggingface.co/spaces/gonzalojduran/Secasol26` |
| Repo GitHub (privado) | `https://github.com/gonzalo-duran/Secasol26-secadores-solares` |
| Documentación HF Spaces + Streamlit | `https://huggingface.co/docs/hub/en/spaces-sdks-streamlit` |

---

## 141. Notas de seguridad

- Un token de Hugging Face (tipo Write) fue expuesto accidentalmente en el chat durante la sesión. Fue **revocado inmediatamente** al finalizar la configuración y reemplazado por uno nuevo.
- El token nuevo se almacenó como secreto `HF_TOKEN` en GitHub Actions — nunca en el código.

---

## 142. Pendiente para siguientes sesiones

- Heredados de S30: validación cruzada motor TD vs capa fina, poblar catálogo de productos, verificar k de manzana, commit de trabajo de S23+S24 pendiente.
- **Opcional:** considerar desvinculación de Streamlit Community Cloud (app.streamlit.io → Delete app) si ya no se usa.
- **Cold start de HF Spaces:** la app se "duerme" tras un período de inactividad en el tier gratuito. El primer acceso tras el sleep tarda ~1-2 minutos. No es un bug, es comportamiento normal del tier Free.
