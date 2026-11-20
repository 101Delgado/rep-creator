import os
import pandas as pd
import function_dataframe as fd 
import github_manager as gm
import time
from dotenv import load_dotenv

def asignar_colaborador_defecto_a_todos(
    df: pd.DataFrame,
    col_grupo: str,
    owner: str,
    headers: dict[str, str],
    colaborador_defecto: str,
    org: str | None = None,
    pausa_segundos: int = 4,
) -> None:
    if not colaborador_defecto or colaborador_defecto.strip().lower() == owner.lower():
        print("[AVISO] Colaborador por defecto vacío o igual al dueño de la cuenta.")
        return

    grupos_unicos = df[col_grupo].dropna().unique()
    permiso = "admin" if (org and org.strip()) else "push"
    usuario = colaborador_defecto.strip()

    print(f"\n=== Asignando a '{usuario}' en {len(grupos_unicos)} repositorio(s) ===")

    for grupo in grupos_unicos:
        repo_slug = gm.formatear_nombre_repo(str(grupo))

        if not gm.repositorio_existe(owner, repo_slug, headers):
            print(f"  [OMITIDO] '{owner}/{repo_slug}' no existe en GitHub.")
            continue

        gm.agregar_colaborador(
            owner=owner,
            repo_slug=repo_slug,
            usuario=usuario,
            headers=headers,
            permiso=permiso,
        )
        # Pausa para no disparar de nuevo el secondary rate limit
        time.sleep(pausa_segundos)

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
COLABORADOR_DEFECTO = os.getenv("GITHUB_DEFAULT_COLLABORATOR")
GITHUB_ORG = os.getenv("GITHUB_ORG") or None

if not GITHUB_TOKEN:
    raise ValueError("Falta configurar GITHUB_TOKEN en el archivo .env")

RUTA_CSV = "formulario.csv"
COL_GRUPO = "Nombre del grupo"
COL_USUARIO = "Usuario de GitHub"
COL_AGREGADO = "Agregado al repositorio"

df_init = pd.read_csv(RUTA_CSV)

df_groups = fd.modification_groups(df_init, COL_GRUPO)
df_groups = fd.unificar_categorias(df_groups, COL_GRUPO, umbral=0.80)

grupos_github = fd.agrupar_usuarios_por_grupo(
    df_groups,
    col_grupo= COL_GRUPO,
    col_usuario= COL_USUARIO,
    col_agregado= COL_AGREGADO,
)

headers = gm.construir_headers(GITHUB_TOKEN)
owner = gm.obtener_owner(headers, org=GITHUB_ORG)
print(f"Autenticado en GitHub como: {owner}")

SOLO_COLABORADOR_DEFECTO = False  # Cámbialo a False cuando termines esta pasada

if SOLO_COLABORADOR_DEFECTO:
    asignar_colaborador_defecto_a_todos(
        df=df_groups,
        col_grupo=COL_GRUPO,
        owner=owner,
        headers=headers,
        colaborador_defecto=COLABORADOR_DEFECTO,
        org=GITHUB_ORG,
        pausa_segundos=4,
    )
else:
    
    try:
        for grupo, usuarios in grupos_github.items():
            exitosos = gm.procesar_grupo_en_github(
                nombre_grupo=grupo,
                usuarios=usuarios,
                owner=owner,
                headers=headers,
                colaborador_defecto=COLABORADOR_DEFECTO,
                org=GITHUB_ORG,
            )

            for usuario in exitosos:
                df_groups = fd.actualizar_estado_usuario(
                    df_groups,
                    grupo=grupo,
                    usuario=usuario,
                    col_grupo=COL_GRUPO,
                    col_usuario=COL_USUARIO,
                    col_agregado=COL_AGREGADO,
                )
    finally:
        fd.reemplazar_csv(df_groups, RUTA_CSV)
        time.sleep(10)
        print(f"\nArchivo '{RUTA_CSV}' reemplazado con el DataFrame actualizado.")
    

