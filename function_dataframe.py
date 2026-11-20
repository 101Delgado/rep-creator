import pandas as pd
import re
from difflib import SequenceMatcher
from itertools import combinations

# conjuntos de conectores dentro del castellano e ingles 
CONECTORES = {
    "de", "del", "la", "las", "el", "los",
    "y", "e", "en", "para", "por", "con", "a"
}

# Reglas oficiales de GitHub: 1 a 39 caracteres alfanuméricos o guiones simples (sin guion al inicio/final)
PATRON_GITHUB = re.compile(r"^(?!.*--)[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$")

def modification_groups(df: pd.DataFrame, name_column: str) -> pd.DataFrame:
    """
    funcion que permite:
    1) colocar todos los nombres en minusculas
    2) quitar los caracteres especiales y emojis
    3) quitar espacios antes y despues del texto
    """

    df[name_column] = (
        df[name_column]
        .astype(str)
        .str.lower()
        .str.replace(r"[^a-záéíóúüñ\s]", "", regex=True)
        .str.strip()
    )
    
    return df 

def _firm_base(texto: str) -> str:
    """
    permite extraer los conectores de la palabra y quedarse con el 
    cuerpo de la misma 
    """
    return " ".join(p for p in texto.split() if p not in CONECTORES)

def unificar_categorias(df: pd.DataFrame, name_column: str, umbral: float = 0.85) -> pd.DataFrame:
    """
    la funcion busca:
    1) unificar las palabras cuyos conectores cambian
    2) unicicar las palabras cuyas letras puenden cambiar 

    solo lo hace para palabras o frases que se parecen mucho 
    """
    
    df = df.copy()
    # Ordena de mayor a menor frecuencia en el DataFrame
    categorias = df[name_column].dropna().value_counts().index.tolist()
    reemplazos = {}

    for cat_a, cat_b in combinations(categorias, 2):
        # Si alguna ya fue reemplazada anteriormente, toma su nombre actual
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
            print(f"\nSe encontraron categorías muy parecidas:")
            print(f"  [1] '{cat_a}'")
            print(f"  [2] '{cat_b}'")
            opcion = input("¿Cuál deseas conservar? (1 / 2 / Enter para dejar ambas): ").strip()

            if opcion == "1":
                reemplazos[cat_b] = cat_a
                # Actualiza si otras variantes apuntaban a cat_b
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
) -> dict[str, list[str]]:
    df_valido = df.dropna(subset=[col_grupo]).copy()

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
        print("Advertencia - Usuarios de GitHub inválidos omitidos:")
        for _, fila in invalidos.iterrows():
            print(f"  Grupo '{fila[col_grupo]}': '{fila[col_usuario]}'")

    pendientes = pendientes[mascara_validos]

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