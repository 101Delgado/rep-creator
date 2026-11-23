# RepCreator

<p align="center">
  <strong>Automatización de repositorios y colaboradores en GitHub desde archivos CSV</strong><br>
  <strong>Automated GitHub repository & collaborator management from CSV files</strong>
</p>

<p align="center">
  <a href="#espanol">🇪🇸 Español</a> •
  <a href="#english">🇬🇧 English</a>
</p>

---

<a id="espanol"></a>
## 🇪🇸 Español

**RepCreator** es una aplicación de escritorio en Python diseñada para automatizar la creación masiva de repositorios públicos en GitHub (con licencia **MIT**) y la asignación de colaboradores con permisos de escritura a partir de un archivo `.csv`.

### Características principales

* **Limpieza y normalización de datos:** Estandariza nombres de grupos (minúsculas, eliminación de emojis y caracteres especiales) y detecta categorías similares por errores de escritura o conectores para unificarlas visualmente.
* **Validación de usuarios de GitHub:** Extrae nombres de usuario desde URLs completas o menciones (`@usuario`), elimina duplicados sin distinguir mayúsculas y separa entradas inválidas en una pestaña dedicada.
* **Control de estado persistente:** Lee una columna booleana (`True`/`False`) para invitar únicamente a los estudiantes pendientes y actualiza el archivo `.csv` automáticamente al terminar cada grupo.
* **Permisos y colaborador por defecto:** Configura repositorios públicos con licencia MIT, otorga permiso de escritura (`push`) a los integrantes y permite incluir automáticamente un colaborador por defecto en todos los repositorios (ideal al crear repos desde una cuenta institucional).
* **Protección contra límites de API:** Gestiona pausas configurables y reintentos automáticos (`Retry-After`) frente a bloqueos temporales (*Secondary Rate Limits*) de GitHub.
* **Exportación de resúmenes:** Genera reportes en **Markdown (`.md`)** o **CSV (`.csv`)** con enlaces directos a cada repositorio y a los perfiles de sus integrantes.

### Estructura del proyecto

```text
RepCreator/
├── main.py                  # Lanzador principal de la interfaz gráfica
├── function_dataframe.py    # Limpieza de datos, unificación, CSV y exportación de resúmenes
├── github_manager.py        # Integración con la API REST de GitHub y control de rate limits
├── requirements.txt         # Dependencias de Python
└── .env.example             # Plantilla de variables de entorno
```

### Requisitos e instalación

Requiere **Python 3.10 o superior**.

1. **Clona el repositorio:**
   ```bash
   git clone [https://github.com/](https://github.com/)<tu-usuario>/rep-creator.git
   cd rep-creator
   ```

2. **Crea y activa un entorno virtual:**
   * **Windows (PowerShell):**
     ```powershell
     python -m venv .venv
     .venv\Scripts\Activate.ps1
     ```
   * **Linux / macOS:**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Instala las dependencias:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Dependencias incluidas: `pandas`, `requests` y `python-dotenv`. `tkinter` viene integrado con Python; en Ubuntu/Debian puede requerir `sudo apt install python3-tk`).*

### Configuración del archivo `.env`

Crea un archivo llamado exactamente `.env` en la raíz del proyecto (puedes duplicar `.env.example`) y coloca tus variables sin espacios alrededor del `=` ni comillas:

```env
GITHUB_TOKEN=ghp_pega_aqui_tu_token_de_github
GITHUB_DEFAULT_COLLABORATOR=tu_usuario_personal
GITHUB_ORG=
```

| Variable | Obligatoria | Descripción |
| :--- | :---: | :--- |
| `GITHUB_TOKEN` | Sí | Token de acceso personal de la cuenta dueña de los repositorios. |
| `GITHUB_DEFAULT_COLLABORATOR` | No | Usuario de GitHub que se agregará automáticamente a todos los repositorios creados (sin `@`). |
| `GITHUB_ORG` | No | Nombre de la Organización de GitHub. **Déjalo vacío** si los repositorios se crearán en una cuenta de usuario normal. |

> **Seguridad:** Asegúrate de que `.env` esté listado en tu archivo `.gitignore` para nunca subir tu token a un repositorio público.

### Cómo obtener tu Token de GitHub

Inicia sesión en GitHub con la cuenta que creará los repositorios:

#### Opción A: Personal Access Token (Classic) — Recomendado
1. Haz clic en tu foto de perfil (esquina superior derecha) y entra en **Settings**.
2. En el menú lateral izquierdo, baja hasta el final y selecciona **Developer settings**.
3. Abre **Personal access tokens** → **Tokens (classic)**.
4. Haz clic en **Generate new token** → **Generate new token (classic)**.
5. Asigna un nombre en **Note** (ej. `RepCreator`) y define la fecha de expiración en **Expiration**.
6. En **Select scopes**, marca la casilla principal **`repo`**.
7. Haz clic en **Generate token**, copia el código (`ghp_...`) de inmediato y pégalo en `GITHUB_TOKEN` dentro de tu `.env`.

#### Opción B: Fine-grained Token (permisos granulares)
1. En **Developer settings** → **Personal access tokens** → **Fine-grained tokens**, pulsa **Generate new token**.
2. En **Repository access**, selecciona **All repositories**.
3. En **Repository permissions**, otorga acceso **Read and write** a **Administration** y a **Contents**.
4. Genera el token (`github_pat_...`) y pégalo en `GITHUB_TOKEN`.

#### Verificación rápida del token
Con el entorno virtual activo, comprueba que Python lee tu `.env` y se autentica correctamente:

```bash
python -c "import os, requests; from dotenv import load_dotenv; load_dotenv(); r = requests.get('[https://api.github.com/user](https://api.github.com/user)', headers={'Authorization': f'Bearer {os.getenv(\"GITHUB_TOKEN\")}'}); print(r.status_code, r.json().get('login'))"
```

Si la salida muestra `200` seguido del nombre de usuario de la cuenta, la conexión está lista.

### Formato del archivo CSV

Tu archivo `.csv` puede tener cualquier cantidad de columnas, pero debe incluir al menos tres columnas seleccionables desde la interfaz:

| Nombre del grupo | Usuario de GitHub | Agregado al repositorio |
| :--- | :--- | :--- |
| Equipo Alpha | `https://github.com/estudiante1` | `False` |
| equipo alpha | `@estudiante2` | `False` |
| Equipo Beta | `estudiante3` | `True` |

* Los valores aceptados como pendientes en la columna booleana son `False`, `FALSO` o `0`.
* Cierra el archivo en Excel antes de iniciar la ejecución para evitar errores de permisos al actualizarlo.

### Uso

Abre una terminal en la carpeta raíz del proyecto con el entorno virtual activo y ejecuta:

```bash
python main.py
```

**Flujo dentro de la aplicación:**
1. Selecciona tu `.csv`, verifica las columnas asignadas y pulsa **Cargar y Analizar CSV**.
2. Si existen grupos con nombres muy similares, revísalos en la pestaña **Unificar Categorías** y pulsa **Aplicar Unificaciones**.
3. Verifica tu conexión con el botón superior **Verificar conexión GitHub**.
4. Pulsa **Crear Repos y Asignar Pendientes** (o **Solo asignar colaborador por defecto** si los repos ya existen).
5. Usa **Exportar Resumen con Links** para generar tu tabla final en `.md` o `.csv`.

### Licencia

Este proyecto se distribuye bajo la licencia **MIT**.

---

<a id="english"></a>
## 🇬🇧 English

**RepCreator** is a Python desktop application designed to automate the bulk creation of public GitHub repositories (**MIT** licensed) and the assignment of collaborators with write permissions from a `.csv` file.

### Key Features

* **Data Cleaning & Normalization:** Standardizes group names (lowercase, strips emojis and special characters) and detects similar group names caused by typos or stop words for visual unification.
* **GitHub Username Validation:** Extracts usernames from full profile URLs or `@mentions`, deduplicates case-insensitively, and isolates invalid entries in a dedicated tab.
* **Persistent State Tracking:** Reads a boolean column (`True`/`False`) to invite only pending users and automatically updates the `.csv` file after processing each group.
* **Permissions & Default Collaborator:** Creates public MIT-licensed repositories, grants write (`push`) access to members, and supports automatically adding a default collaborator to every repository (useful when creating repos under an institutional account).
* **API Rate-Limit Protection:** Handles configurable delays and automatic retries (`Retry-After`) against GitHub Secondary Rate Limits.
* **Summary Export:** Generates ready-to-share **Markdown (`.md`)** or **CSV (`.csv`)** reports containing direct links to each repository and its members' profiles.

### Project Structure

```text
RepCreator/
├── main.py                  # Main launcher for the graphical interface
├── function_dataframe.py    # Data cleaning, unification, CSV handling, and report export
├── github_manager.py        # GitHub REST API integration and rate-limit handling
├── requirements.txt         # Python dependencies
└── .env.example             # Environment variables template
```

### Requirements & Installation

Requires **Python 3.10 or higher**.

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/](https://github.com/)<your-username>/rep-creator.git
   cd rep-creator
   ```

2. **Create and activate a virtual environment:**
   * **Windows (PowerShell):**
     ```powershell
     python -m venv .venv
     .venv\Scripts\Activate.ps1
     ```
   * **Linux / macOS:**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Dependencies: `pandas`, `requests`, and `python-dotenv`. `tkinter` is included with Python; on Ubuntu/Debian you may need `sudo apt install python3-tk`.)*

### Environment File Configuration (`.env`)

Create a file named `.env` in the project root (you can copy `.env.example`) and add your values with no spaces around `=` and no quotes:

```env
GITHUB_TOKEN=ghp_paste_your_github_token_here
GITHUB_DEFAULT_COLLABORATOR=your_personal_username
GITHUB_ORG=
```

| Variable | Required | Description |
| :--- | :---: | :--- |
| `GITHUB_TOKEN` | Yes | Personal Access Token for the account that will own the repositories. |
| `GITHUB_DEFAULT_COLLABORATOR` | No | GitHub username automatically added to every created repository (without `@`). |
| `GITHUB_ORG` | No | GitHub Organization name. **Leave empty** if creating repositories under a standard user account. |

> **Security:** Make sure `.env` is listed in your `.gitignore` so your token is never committed to version control.

### How to Generate a GitHub Token

Sign in to GitHub with the account that will own the repositories:

#### Option A: Personal Access Token (Classic) — Recommended
1. Click your profile picture (top-right corner) and open **Settings**.
2. Scroll down the left sidebar and click **Developer settings**.
3. Navigate to **Personal access tokens** → **Tokens (classic)**.
4. Click **Generate new token** → **Generate new token (classic)**.
5. Enter a descriptive **Note** (e.g., `RepCreator`) and choose an **Expiration** period.
6. Under **Select scopes**, check the **`repo`** checkbox.
7. Click **Generate token**, copy the generated string (`ghp_...`) immediately, and paste it into `GITHUB_TOKEN` inside your `.env` file.

#### Option B: Fine-grained Token
1. Go to **Developer settings** → **Personal access tokens** → **Fine-grained tokens** and click **Generate new token**.
2. Under **Repository access**, select **All repositories**.
3. Under **Repository permissions**, grant **Read and write** access to **Administration** and **Contents**.
4. Generate the token (`github_pat_...`) and paste it into `GITHUB_TOKEN`.

#### Quick Token Check
With your virtual environment active, verify that Python reads `.env` and authenticates properly:

```bash
python -c "import os, requests; from dotenv import load_dotenv; load_dotenv(); r = requests.get('[https://api.github.com/user](https://api.github.com/user)', headers={'Authorization': f'Bearer {os.getenv(\"GITHUB_TOKEN\")}'}); print(r.status_code, r.json().get('login'))"
```

A `200` status code followed by the account username confirms the setup is ready.

### Expected CSV Format

Your `.csv` file can contain any number of columns, as long as it includes at least three columns selectable in the UI:

| Group Name | GitHub Username | Added to Repo |
| :--- | :--- | :--- |
| Team Alpha | `https://github.com/student1` | `False` |
| team alpha | `@student2` | `False` |
| Team Beta | `student3` | `True` |

* Values recognized as pending in the boolean column: `False`, `FALSO`, or `0`.
* Close the CSV file in Excel before running the tool to prevent file-lock permission errors when saving progress.

### Usage

Open a terminal in the project root directory with the virtual environment activated and run:

```bash
python main.py
```

**In-App Workflow:**
1. Select your `.csv` file, map the three required columns, and click **Cargar y Analizar CSV**.
2. If similar group names are detected, review them in the **Unificar Categorías** tab and apply your selections.
3. Click **Verificar conexión GitHub** to confirm your credentials.
4. Click **Crear Repos y Asignar Pendientes** (or **Solo asignar colaborador por defecto** to add the default collaborator across existing repositories).
5. Click **Exportar Resumen con Links** to save the final `.md` or `.csv` summary report.

### License

This project is distributed under the **MIT** License.
