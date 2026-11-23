import re
import threading
import time
import unicodedata
from collections.abc import Callable
import pandas as pd
import requests

GITHUB_API_URL = "https://api.github.com"


def _esperar(segundos: float, stop_event: threading.Event | None = None) -> bool:
    """Espera sin bloquear una cancelación. Devuelve True si se solicitó detener."""
    if stop_event is None:
        time.sleep(segundos)
        return False
    return stop_event.wait(timeout=segundos)


def construir_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def formatear_nombre_repo(nombre_grupo: str) -> str:
    """Convierte el nombre limpio del grupo en un slug válido para GitHub."""
    sin_tildes = (
        unicodedata.normalize("NFKD", nombre_grupo)
        .encode("ascii", "ignore")
        .decode("utf-8")
    )
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", sin_tildes.strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug


def obtener_owner(headers: dict[str, str], org: str | None = None) -> str:
    """Devuelve el nombre de la organización o del usuario dueño del token."""
    if org and org.strip():
        return org.strip()

    resp = requests.get(f"{GITHUB_API_URL}/user", headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()["login"]


def _peticion_segura(
    metodo: str,
    url: str,
    headers: dict[str, str],
    json: dict | None = None,
    timeout: int = 20,
    max_reintentos: int = 4,
    on_log: Callable[[str], None] = print,
    stop_event: threading.Event | None = None,
) -> requests.Response:
    """Ejecuta una petición HTTP respetando Retry-After ante límites secundarios."""
    resp = None
    for intento in range(1, max_reintentos + 1):
        resp = requests.request(
            metodo, url, headers=headers, json=json, timeout=timeout
        )

        es_limite_secundario = resp.status_code == 429 or (
            resp.status_code == 403 and "rate limit" in resp.text.lower()
        )

        if not es_limite_secundario or intento == max_reintentos:
            return resp

        retry_after = resp.headers.get("Retry-After")
        espera = int(retry_after) + 5 if retry_after and retry_after.isdigit() else 60 * intento

        on_log(
            f"  [RATE LIMIT] GitHub pausó temporalmente la cuenta. "
            f"Esperando {espera}s antes del reintento {intento}/{max_reintentos - 1}..."
        )
        if _esperar(espera, stop_event):
            on_log("  [DETENIDO] Espera cancelada por el usuario.")
            return resp

    return resp


def repositorio_existe(owner: str, repo_slug: str, headers: dict[str, str]) -> bool:
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo_slug}"
    resp = requests.get(url, headers=headers, timeout=15)
    if resp.status_code == 200:
        return True
    if resp.status_code == 404:
        return False
    resp.raise_for_status()
    return False


def crear_repositorio(
    repo_slug: str,
    headers: dict[str, str],
    org: str | None = None,
    descripcion: str = "",
    on_log: Callable[[str], None] = print,
    stop_event: threading.Event | None = None,
) -> bool:
    url = (
        f"{GITHUB_API_URL}/orgs/{org.strip()}/repos"
        if org and org.strip()
        else f"{GITHUB_API_URL}/user/repos"
    )

    payload = {
        "name": repo_slug,
        "description": descripcion,
        "private": False,
        "license_template": "mit",
        "auto_init": True,
    }

    resp = _peticion_segura(
        "POST", url, headers=headers, json=payload, timeout=20,
        on_log=on_log, stop_event=stop_event
    )
    if resp.status_code == 201:
        on_log(f"[CREADO] Repositorio público '{repo_slug}' (Licencia MIT).")
        return True

    on_log(f"[ERROR] No se pudo crear '{repo_slug}' ({resp.status_code}): {resp.text}")
    return False


def agregar_colaborador(
    owner: str,
    repo_slug: str,
    usuario: str,
    headers: dict[str, str],
    permiso: str | None = "push",
    on_log: Callable[[str], None] = print,
    stop_event: threading.Event | None = None,
) -> bool:
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo_slug}/collaborators/{usuario}"
    payload = {"permission": permiso} if permiso else None

    resp = _peticion_segura(
        "PUT", url, headers=headers, json=payload, timeout=15,
        on_log=on_log, stop_event=stop_event
    )

    if resp.status_code == 201:
        permiso_confirmado = resp.json().get("permissions", "write")
        on_log(f"  [INVITADO] {usuario} -> {owner}/{repo_slug} (permiso: {permiso_confirmado})")
        return True

    if resp.status_code == 204:
        on_log(f"  [YA EXISTÍA] {usuario} ya tiene acceso en {owner}/{repo_slug}")
        return True

    mensaje = resp.json().get("message", resp.text) if resp.text else resp.status_code
    on_log(f"  [ERROR] No se pudo agregar a '{usuario}' ({resp.status_code}): {mensaje}")
    return False


def procesar_grupo_en_github(
    nombre_grupo: str,
    usuarios: list[str],
    owner: str,
    headers: dict[str, str],
    colaborador_defecto: str | None = None,
    org: str | None = None,
    on_log: Callable[[str], None] = print,
    on_repo_existente: Callable[[str, str], bool] | None = None,
    stop_event: threading.Event | None = None,
) -> list[str]:
    """
    Crea el repositorio si no existe (o consulta mediante on_repo_existente / consola),
    asigna al colaborador por defecto y a cada estudiante con permiso de escritura.
    """
    repo_slug = formatear_nombre_repo(nombre_grupo)
    on_log(f"\n--- Procesando grupo: '{nombre_grupo}' (repo: {owner}/{repo_slug}) ---")

    if stop_event and stop_event.is_set():
        return []

    if repositorio_existe(owner, repo_slug, headers):
        on_log(f"[AVISO] El repositorio '{owner}/{repo_slug}' ya existe en GitHub.")
        if on_repo_existente is not None:
            continuar = on_repo_existente(owner, repo_slug)
        else:
            respuesta = (
                input("¿Deseas agregar los usuarios pendientes a este repositorio existente? (s/n): ")
                .strip()
                .lower()
            )
            continuar = respuesta in {"s", "si", "sí", "y", "yes"}

        if not continuar:
            on_log(f"[OMITIDO] Se saltó la asignación de usuarios para '{repo_slug}'.")
            return []
    else:
        creado = crear_repositorio(
            repo_slug=repo_slug,
            headers=headers,
            org=org,
            descripcion=f"Repositorio del grupo {nombre_grupo}",
            on_log=on_log,
            stop_event=stop_event,
        )
        if not creado:
            return []
        if _esperar(5, stop_event):
            return []

    es_org = bool(org and org.strip())

    # 1. Colaborador por defecto (admin en Org, push en cuenta personal)
    if colaborador_defecto and colaborador_defecto.strip().lower() != owner.lower():
        permiso_defecto = "admin" if es_org else "push"
        on_log(f"  Agregando colaborador por defecto ({colaborador_defecto.strip()})...")
        agregar_colaborador(
            owner=owner,
            repo_slug=repo_slug,
            usuario=colaborador_defecto.strip(),
            headers=headers,
            permiso=permiso_defecto,
            on_log=on_log,
            stop_event=stop_event,
        )
        if _esperar(3, stop_event):
            return []

    # 2. Estudiantes pendientes siempre con permiso explícito de escritura ("push")
    agregados_exitosamente: list[str] = []

    for usuario in usuarios:
        if stop_event and stop_event.is_set():
            break

        if usuario.lower() == owner.lower():
            agregados_exitosamente.append(usuario)
            continue

        ok = agregar_colaborador(
            owner=owner,
            repo_slug=repo_slug,
            usuario=usuario,
            headers=headers,
            permiso="push",
            on_log=on_log,
            stop_event=stop_event,
        )
        if ok:
            agregados_exitosamente.append(usuario)

        if _esperar(3, stop_event):
            break

    return agregados_exitosamente


def asignar_colaborador_defecto_a_todos(
    df: pd.DataFrame,
    col_grupo: str,
    owner: str,
    headers: dict[str, str],
    colaborador_defecto: str,
    org: str | None = None,
    pausa_segundos: int = 4,
    on_log: Callable[[str], None] = print,
    on_progreso: Callable[[int, int, str], None] | None = None,
    stop_event: threading.Event | None = None,
) -> None:
    if not colaborador_defecto or colaborador_defecto.strip().lower() == owner.lower():
        on_log("[AVISO] Colaborador por defecto vacío o igual al dueño de la cuenta.")
        return

    grupos_unicos = [str(g) for g in df[col_grupo].dropna().unique() if str(g).strip()]
    total = len(grupos_unicos)
    permiso = "admin" if (org and org.strip()) else "push"
    usuario = colaborador_defecto.strip()

    on_log(f"\n=== Asignando a '{usuario}' en {total} repositorio(s) ===")

    for idx, grupo in enumerate(grupos_unicos, start=1):
        if stop_event and stop_event.is_set():
            on_log("[DETENIDO] Asignación de colaborador por defecto interrumpida.")
            break

        repo_slug = formatear_nombre_repo(grupo)
        if on_progreso:
            on_progreso(idx, total, f"Verificando {repo_slug}...")

        if not repositorio_existe(owner, repo_slug, headers):
            on_log(f"  [OMITIDO] '{owner}/{repo_slug}' no existe en GitHub.")
            continue

        agregar_colaborador(
            owner=owner,
            repo_slug=repo_slug,
            usuario=usuario,
            headers=headers,
            permiso=permiso,
            on_log=on_log,
            stop_event=stop_event,
        )
        if _esperar(pausa_segundos, stop_event):
            break