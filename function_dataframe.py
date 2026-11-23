import re
from collections.abc import Callable
from difflib import SequenceMatcher
from itertools import combinations
import pandas as pd

# Conjuntos de conectores dentro del castellano e inglés
CONECTORES = {
    "de", "del", "la", "las", "el", "los",
    "y", "e", "en", "para", "por", "con", "a"
}

# Reglas oficiales de GitHub: 1 a 39 caracteres alfanuméricos o guiones simples (sin guion al inicio/final)
PATRON_GITHUB = re.compile(r"^(?!.*--)[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$")


def modification_groups(df: pd.DataFrame, name_column: str) -> pd.DataFrame:
    """
    Normaliza los nombres de grupo en una copia del DataFrame sin alterar celdas vacías:
    1) coloca todos los nombres en minúsculas
    2) quita caracteres especiales y emojis
    3) quita espacios antes y después del texto
    """
    df = df.copy()
    no_nulos = df[name_column].notna()

    df.loc[no_nulos, name_column] = (
        df.loc[no_nulos, name_column]
        .astype(str)
        .str.lower()
        .str.replace(r"[^a-záéíóúüñ\s]", "", regex=True)
        .str.strip()
    )

    return df


def _firm_base(texto: str) -> str:
    """
    Extrae los conectores de la frase y devuelve el núcleo de palabras clave.
    """
    return " ".join(p for p in texto.split() if p not in CONECTORES)


def detectar_pares_similares(
    df: pd.DataFrame, name_column: str, umbral: float = 0.85
) -> list[tuple[str, str, float]]:
    """
    Devuelve una lista de tuplas (cat_mas_frecuente, cat_variante, similitud)
    para mostrarlas en la interfaz gráfica sin bloquear con input().
    """
    categorias = df[name_column].dropna().value_counts().index.tolist()
    pares: list[tuple[str, str, float]] = []

    for cat_a, cat_b in combinations(categorias, 2):
        firma_a = _firm_base(cat_a)
        firma_b = _firm_base(cat_b)

        mismo_nucleo = (firma_a == firma_b) and (firma_a != "")
        similitud_nucleo = SequenceMatcher(None, firma_a, firma_b).ratio()
        similitud_total = SequenceMatcher(None, cat_a, cat_b).ratio()
        similitud = 1.0 if mismo_nucleo else max(similitud_nucleo, similitud_total)

        if mismo_nucleo or similitud >= umbral:
            pares.append((cat_a, cat_b, similitud))

    return pares


def aplicar_reemplazos_categorias(
    df: pd.DataFrame, name_column: str, reemplazos: dict[str, str]
) -> pd.DataFrame:
    """
    Aplica un diccionario de reemplazos resolviendo cadenas transitivas (C -> B -> A).
    """
    if not reemplazos:
        return df.copy()

    mapa_final: dict[str, str] = {}
    for origen, destino in reemplazos.items():
        visitados = {origen}
        actual = destino
        while actual in reemplazos and actual not in visitados:
            visitados.add(actual)
            actual = reemplazos[actual]
        mapa_final[origen] = actual

    df = df.copy()
    df[name_column] = df[name_column].replace(mapa_final)
    return df


def unificar_categorias(df: pd.DataFrame, name_column: str, umbral: float = 0.85) -> pd.DataFrame:
    """
    Versión interactiva por consola (conservada para compatibilidad con main.py):
    1) unifica palabras cuyos conectores cambian
    2) unifica palabras cuyas letras tienen diferencias mínimas
    """
    df = df.copy()
    categorias = df[name_column].dropna().value_counts().index.tolist()
    reemplazos: dict[str, str] = {}

    for cat_a, cat_b in combinations(categorias, 2):
        while cat_a in reemplazos:
            cat_a = reemplazos[cat_a]
        while cat_b in reemplazos:
            cat_b = reemplazos[cat_b]

        if cat_a == cat_b:
            continue

        firma_a = _firm_base(cat_a)
        firma_b = _firm_base(cat_b)

        mismo_nucleo = (firma_a == firma_b) and (firma_a != "")
        similitud_nucleo = SequenceMatcher(None, firma_a, firma_b).ratio()
        similitud_total = SequenceMatcher(None, cat_a, cat_b).ratio()

        if mismo_nucleo or max(similitud_nucleo, similitud_total) >= umbral:
            print("\nSe encontraron categorías muy parecidas:")
            print(f"  [1] '{cat_a}'")
            print(f"  [2] '{cat_b}'")
            opcion = input("¿Cuál deseas conservar? (1 / 2 / Enter para dejar ambas): ").strip()

            if opcion == "1":
                reemplazos[cat_b] = cat_a
                for k, v in reemplazos.items():
                    if v == cat_b:
                        reemplazos[k] = cat_a
            elif opcion == "2":
                reemplazos[cat_a] = cat_b
                for k, v in reemplazos.items():
                    if v == cat_a:
                        reemplazos[k] = cat_b

    if reemplazos:
        df[name_column] = df[name_column].replace(reemplazos)
        print(f"\nSe unificaron {len(reemplazos)} categoría(s).")

    return df


def _limpiar_usuario_github(valor: str) -> str:
    texto = str(valor).strip()

    # Extrae el username si pegaron la URL completa (ej. https://github.com/usuario/repo)
    coincidencia_url = re.search(r"github\.com/([^/\s?#]+)", texto, re.IGNORECASE)
    if coincidencia_url:
        texto = coincidencia_url.group(1)

    # Quita prefijos como "@usuario" o barras sobrantes
    return texto.lstrip("@").strip("/")


def _es_false(valor) -> bool:
    if pd.isna(valor):
        return False
    return str(valor).strip().lower() in {"false", "falso", "0", "0.0"}


def _usuarios_unicos(serie: pd.Series) -> list[str]:
    # GitHub no distingue mayúsculas/minúsculas en usernames, evita duplicados como "Juan" y "juan"
    vistos = set()
    resultado = []
    for usuario in serie:
        clave = usuario.lower()
        if clave not in vistos:
            vistos.add(clave)
            resultado.append(usuario)
    return resultado


def agrupar_usuarios_por_grupo(
    df: pd.DataFrame,
    col_grupo: str,
    col_usuario: str,
    col_agregado: str,
    incluir_grupos_vacios: bool = True,
    on_log: Callable[[str], None] = print,
    invalidos_out: list[tuple[str, str]] | None = None,
) -> dict[str, list[str]]:
    df_valido = df.dropna(subset=[col_grupo]).copy()
    df_valido = df_valido[df_valido[col_grupo].astype(str).str.strip() != ""]

    # Conserva todos los grupos como clave aunque ya no tengan estudiantes pendientes
    diccionario_grupos: dict[str, list[str]] = (
        {grupo: [] for grupo in df_valido[col_grupo].unique()}
        if incluir_grupos_vacios
        else {}
    )

    # Filtra solo filas con usuario y estado False en la columna booleana
    pendientes = df_valido[
        df_valido[col_usuario].notna() & df_valido[col_agregado].apply(_es_false)
    ].copy()

    pendientes[col_usuario] = pendientes[col_usuario].apply(_limpiar_usuario_github)

    mascara_validos = pendientes[col_usuario].str.match(PATRON_GITHUB)
    invalidos = pendientes.loc[~mascara_validos, [col_grupo, col_usuario]]

    if not invalidos.empty:
        on_log("[AVISO] Usuarios de GitHub inválidos omitidos:")
        for _, fila in invalidos.iterrows():
            grupo_inv = str(fila[col_grupo])
            user_inv = str(fila[col_usuario])
            on_log(f"  Grupo '{grupo_inv}': '{user_inv}'")
            if invalidos_out is not None:
                invalidos_out.append((grupo_inv, user_inv))

    pendientes = pendientes[mascara_validos]

    if not pendientes.empty:
        agrupados = (
            pendientes.groupby(col_grupo, sort=False)[col_usuario]
            .apply(_usuarios_unicos)
            .to_dict()
        )
        diccionario_grupos.update(agrupados)

    return diccionario_grupos


def actualizar_estado_usuario(
    df: pd.DataFrame,
    grupo: str,
    usuario: str,
    col_grupo: str,
    col_usuario: str,
    col_agregado: str,
) -> pd.DataFrame:
    df = df.copy()

    # Compara usando el username limpio (sin importar URLs, @ o mayúsculas)
    usuarios_norm = (
        df[col_usuario]
        .fillna("")
        .apply(lambda u: _limpiar_usuario_github(u).lower())
    )

    mascara = (df[col_grupo] == grupo) & (usuarios_norm == usuario.lower())

    # Convierte la columna a booleanos reales si Pandas la leyó como texto ("FALSE"/"FALSO")
    if not pd.api.types.is_bool_dtype(df[col_agregado]):
        df[col_agregado] = ~df[col_agregado].apply(_es_false)

    df.loc[mascara, col_agregado] = True
    return df


def reemplazar_csv(df: pd.DataFrame, ruta_csv: str) -> None:
    # Sobrescribe todo el archivo con el nuevo DataFrame limpio y actualizado
    df.to_csv(ruta_csv, index=False, encoding="utf-8-sig")


def generar_resumen_integrantes(
    df: pd.DataFrame,
    col_grupo: str,
    col_usuario: str,
    col_agregado: str,
    owner: str,
    formatear_slug_fn: Callable[[str], str],
) -> list[dict]:
    """
    Construye el resumen completo por grupo con todos los integrantes válidos,
    su estado (agregado/pendiente) y el enlace directo al repositorio en GitHub.
    """
    df_valido = df.dropna(subset=[col_grupo]).copy()
    df_valido = df_valido[df_valido[col_grupo].astype(str).str.strip() != ""]

    resumen: list[dict] = []

    for grupo, bloque in df_valido.groupby(col_grupo, sort=False):
        grupo_str = str(grupo)
        repo_slug = formatear_slug_fn(grupo_str)
        url_repo = f"https://github.com/{owner}/{repo_slug}"

        # Deduplica sin distinguir mayúsculas; si una fila ya es True, conserva True
        integrantes_map: dict[str, tuple[str, bool]] = {}

        for _, fila in bloque.iterrows():
            val_user = fila[col_usuario]
            if pd.isna(val_user):
                continue

            usuario = _limpiar_usuario_github(val_user)
            if not PATRON_GITHUB.match(usuario):
                continue

            agregado = not _es_false(fila[col_agregado])
            clave = usuario.lower()

            if clave not in integrantes_map or agregado:
                integrantes_map[clave] = (usuario, agregado)

        todos = [u for u, _ in integrantes_map.values()]
        agregados = [u for u, ok in integrantes_map.values() if ok]
        pendientes = [u for u, ok in integrantes_map.values() if not ok]

        resumen.append(
            {
                "grupo": grupo_str,
                "repositorio": repo_slug,
                "url": url_repo,
                "integrantes": todos,
                "agregados": agregados,
                "pendientes": pendientes,
            }
        )

    return resumen


def exportar_resumen_integrantes(resumen: list[dict], ruta_salida: str) -> None:
    """Exporta el resumen con enlaces en formato Markdown (.md) o CSV (.csv)."""
    if ruta_salida.lower().endswith(".md"):
        lineas = [
            "# Resumen de Repositorios e Integrantes",
            "",
            "| Grupo | Repositorio | Integrantes | Estado |",
            "| :--- | :--- | :--- | :---: |",
        ]

        for item in resumen:
            enlace_repo = f"[{item['repositorio']}]({item['url']})"
            if item["integrantes"]:
                enlaces_users = ", ".join(
                    f"[@{u}](https://github.com/{u})" for u in item["integrantes"]
                )
            else:
                enlaces_users = "Sin integrantes válidos"

            estado = f"{len(item['agregados'])}/{len(item['integrantes'])} agregados"
            lineas.append(f"| {item['grupo']} | {enlace_repo} | {enlaces_users} | {estado} |")

        with open(ruta_salida, "w", encoding="utf-8") as f:
            f.write("\n".join(lineas) + "\n")
    else:
        filas = [
            {
                "Grupo": item["grupo"],
                "Repositorio": item["repositorio"],
                "Enlace": item["url"],
                "Integrantes": ", ".join(item["integrantes"]),
                "Total Integrantes": len(item["integrantes"]),
                "Agregados": len(item["agregados"]),
                "Pendientes": len(item["pendientes"]),
            }
            for item in resumen
        ]
        pd.DataFrame(filas).to_csv(ruta_salida, index=False, encoding="utf-8-sig")