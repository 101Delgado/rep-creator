import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
from dotenv import load_dotenv

import function_dataframe as fd
import github_manager as gm

# Paleta limpia de alto contraste (modo oscuro)
BG_MAIN = "#0F172A"
BG_PANEL = "#1E293B"
BG_INPUT = "#0B1220"
FG_TEXT = "#F8FAFC"
FG_MUTED = "#94A3B8"
ACCENT = "#2563EB"
ACCENT_HOVER = "#1D4ED8"
SUCCESS = "#22C55E"
WARNING = "#F59E0B"
DANGER = "#EF4444"
BORDER = "#334155"


class RepCreatorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        load_dotenv()

        self.title("RepCreator — Gestor Automático de Repositorios GitHub")
        self.geometry("1180x740")
        self.minsize(1020, 650)
        self.configure(bg=BG_MAIN)

        # Estado en memoria
        self.df_groups: pd.DataFrame | None = None
        self.grupos_github: dict[str, list[str]] = {}
        self.invalidos: list[tuple[str, str]] = []
        self.pares_similares: list[dict] = []
        self.owner_actual: str | None = None

        # Concurrencia
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.stop_event = threading.Event()
        self.en_ejecucion = False

        # Variables de interfaz
        self.ruta_csv_var = tk.StringVar(
            value="formulario.csv" if os.path.exists("formulario.csv") else ""
        )
        self.col_grupo_var = tk.StringVar(value="Nombre del grupo")
        self.col_usuario_var = tk.StringVar(value="Usuario de GitHub")
        self.col_agregado_var = tk.StringVar(value="Agregado al repositorio")

        self.token_var = tk.StringVar(value=os.getenv("GITHUB_TOKEN", ""))
        self.colaborador_defecto_var = tk.StringVar(
            value=os.getenv("GITHUB_DEFAULT_COLLABORATOR", "")
        )
        self.org_var = tk.StringVar(value=os.getenv("GITHUB_ORG", ""))
        self.umbral_var = tk.DoubleVar(value=0.80)
        self.pausa_grupos_var = tk.IntVar(value=8)
        self.auto_existentes_var = tk.BooleanVar(value=False)

        self.status_conexion_var = tk.StringVar(value="Sin verificar")
        self.status_progreso_var = tk.StringVar(value="Listo para comenzar.")
        self.metricas_var = tk.StringVar(
            value="Filas: 0  |  Grupos: 0  |  Pendientes: 0  |  Inválidos: 0"
        )

        self._configurar_estilos()
        self._construir_ui()
        self.after(100, self._procesar_cola_logs)

        if self.ruta_csv_var.get():
            self._cargar_encabezados_csv(self.ruta_csv_var.get())

        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)

    # ------------------------------------------------------------------
    # Estilos y construcción de UI
    # ------------------------------------------------------------------
    def _configurar_estilos(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")

        self.option_add("*TCombobox*Listbox.background", BG_INPUT)
        self.option_add("*TCombobox*Listbox.foreground", FG_TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.option_add("*TCombobox*Listbox.selectForeground", FG_TEXT)

        style.configure(".", background=BG_MAIN, foreground=FG_TEXT, font=("Segoe UI", 9))
        style.configure("Panel.TFrame", background=BG_PANEL)
        style.configure("Main.TFrame", background=BG_MAIN)

        style.configure(
            "Card.TLabelframe",
            background=BG_PANEL,
            foreground="#38BDF8",
            bordercolor=BORDER,
            relief="solid",
            padding=10,
        )
        style.configure(
            "Card.TLabelframe.Label",
            background=BG_PANEL,
            foreground="#38BDF8",
            font=("Segoe UI", 9, "bold"),
        )

        style.configure("Panel.TLabel", background=BG_PANEL, foreground=FG_TEXT)
        style.configure("Muted.TLabel", background=BG_PANEL, foreground=FG_MUTED)
        style.configure("Header.TLabel", background=BG_PANEL, foreground=FG_TEXT, font=("Segoe UI", 13, "bold"))

        style.configure(
            "TEntry",
            fieldbackground=BG_INPUT,
            foreground=FG_TEXT,
            insertcolor=FG_TEXT,
            bordercolor=BORDER,
            padding=4,
        )
        style.configure(
            "TCombobox",
            fieldbackground=BG_INPUT,
            background=BG_PANEL,
            foreground=FG_TEXT,
            arrowcolor=FG_TEXT,
            bordercolor=BORDER,
            padding=4,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", BG_INPUT)],
            foreground=[("readonly", FG_TEXT)],
        )
        style.configure(
            "TSpinbox",
            fieldbackground=BG_INPUT,
            background=BG_PANEL,
            foreground=FG_TEXT,
            arrowcolor=FG_TEXT,
            bordercolor=BORDER,
            padding=3,
        )
        style.configure("Panel.TCheckbutton", background=BG_PANEL, foreground=FG_TEXT)
        style.map("Panel.TCheckbutton", background=[("active", BG_PANEL)])

        # Botones
        style.configure(
            "Primary.TButton",
            background=ACCENT,
            foreground=FG_TEXT,
            font=("Segoe UI", 9, "bold"),
            borderwidth=0,
            padding=(10, 7),
        )
        style.map("Primary.TButton", background=[("active", ACCENT_HOVER), ("disabled", BORDER)])

        style.configure(
            "Secondary.TButton",
            background="#334155",
            foreground=FG_TEXT,
            borderwidth=0,
            padding=(10, 6),
        )
        style.map("Secondary.TButton", background=[("active", "#475569"), ("disabled", "#1E293B")])

        style.configure(
            "Danger.TButton",
            background=DANGER,
            foreground=FG_TEXT,
            font=("Segoe UI", 9, "bold"),
            borderwidth=0,
            padding=(10, 7),
        )
        style.map("Danger.TButton", background=[("active", "#DC2626"), ("disabled", "#450A0A")])

        # Notebook y tablas
        style.configure("TNotebook", background=BG_MAIN, borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=BG_PANEL,
            foreground=FG_MUTED,
            padding=(14, 8),
            font=("Segoe UI", 9, "bold"),
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", ACCENT)],
            foreground=[("selected", FG_TEXT)],
        )

        style.configure(
            "Treeview",
            background=BG_INPUT,
            fieldbackground=BG_INPUT,
            foreground=FG_TEXT,
            rowheight=26,
            bordercolor=BORDER,
        )
        style.configure(
            "Treeview.Heading",
            background=BG_PANEL,
            foreground="#38BDF8",
            font=("Segoe UI", 9, "bold"),
            bordercolor=BORDER,
        )
        style.map("Treeview", background=[("selected", ACCENT)])
        style.configure("Horizontal.TProgressbar", troughcolor=BG_INPUT, background=ACCENT, bordercolor=BORDER)

    def _construir_ui(self) -> None:
        # Barra superior
        header = ttk.Frame(self, style="Panel.TFrame", padding=(16, 12))
        header.pack(fill="x", side="top")

        ttk.Label(header, text="RepCreator", style="Header.TLabel").pack(side="left")
        ttk.Label(
            header,
            text="  |  Automatización de repositorios y colaboradores desde CSV",
            style="Muted.TLabel",
        ).pack(side="left", padx=(6, 0))

        self.btn_verificar = ttk.Button(
            header, text="Verificar conexión GitHub", style="Secondary.TButton", command=self._verificar_conexion
        )
        self.btn_verificar.pack(side="right")

        self.lbl_conexion = ttk.Label(
            header, textvariable=self.status_conexion_var, style="Muted.TLabel", font=("Segoe UI", 9, "bold")
        )
        self.lbl_conexion.pack(side="right", padx=(0, 14))

        # Contenedor principal dividido
        body = ttk.Frame(self, style="Main.TFrame", padding=12)
        body.pack(fill="both", expand=True)

        left_col = ttk.Frame(body, style="Main.TFrame", width=355)
        left_col.pack(side="left", fill="y", padx=(0, 12))
        left_col.pack_propagate(False)

        right_col = ttk.Frame(body, style="Main.TFrame")
        right_col.pack(side="left", fill="both", expand=True)

        self._construir_panel_izquierdo(left_col)
        self._construir_panel_derecho(right_col)

        # Barra inferior de estado y progreso
        footer = ttk.Frame(self, style="Panel.TFrame", padding=(14, 8))
        footer.pack(fill="x", side="bottom")

        ttk.Label(footer, textvariable=self.status_progreso_var, style="Panel.TLabel").pack(side="left")
        self.progress = ttk.Progressbar(footer, mode="determinate", length=280)
        self.progress.pack(side="right")

    def _construir_panel_izquierdo(self, parent: ttk.Frame) -> None:
        # 3. Acciones fijadas abajo para que el botón de GitHub siempre esté visible
        card_run = ttk.LabelFrame(parent, text="3. Acciones en GitHub", style="Card.TLabelframe")
        card_run.pack(side="bottom", fill="x", pady=(8, 0))

        self.btn_ejecutar = ttk.Button(
            card_run,
            text="Crear Repos y Asignar Pendientes",
            style="Primary.TButton",
            command=self._iniciar_procesamiento_repos,
        )
        self.btn_ejecutar.pack(fill="x", pady=(0, 5))

        self.btn_defecto = ttk.Button(
            card_run,
            text="Solo asignar colaborador por defecto",
            style="Secondary.TButton",
            command=self._iniciar_solo_defecto,
        )
        self.btn_defecto.pack(fill="x", pady=(0, 5))

        self.btn_detener = ttk.Button(
            card_run,
            text="Detener y Guardar Progreso",
            style="Danger.TButton",
            command=self._detener_proceso,
            state="disabled",
        )
        self.btn_detener.pack(fill="x")

        # Contenedor con scroll vertical para las secciones 1 y 2
        scroll_box = ttk.Frame(parent, style="Main.TFrame")
        scroll_box.pack(side="top", fill="both", expand=True)

        canvas = tk.Canvas(scroll_box, bg=BG_MAIN, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(scroll_box, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas, style="Main.TFrame")

        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        inner.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(win_id, width=e.width),
        )

        # Permite desplazar con la rueda del ratón sobre el panel izquierdo
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 1. CSV y Columnas
        card_csv = ttk.LabelFrame(inner, text="1. Archivo CSV y Columnas", style="Card.TLabelframe")
        card_csv.pack(fill="x", pady=(0, 8), padx=(0, 4))

        row_file = ttk.Frame(card_csv, style="Panel.TFrame")
        row_file.pack(fill="x", pady=(0, 6))
        ttk.Entry(row_file, textvariable=self.ruta_csv_var).pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(row_file, text="Buscar", style="Secondary.TButton", command=self._seleccionar_csv).pack(side="right")

        ttk.Label(card_csv, text="Columna de Grupo:", style="Muted.TLabel").pack(anchor="w")
        self.cb_grupo = ttk.Combobox(card_csv, textvariable=self.col_grupo_var, state="readonly")
        self.cb_grupo.pack(fill="x", pady=(2, 4))

        ttk.Label(card_csv, text="Columna Usuario GitHub:", style="Muted.TLabel").pack(anchor="w")
        self.cb_usuario = ttk.Combobox(card_csv, textvariable=self.col_usuario_var, state="readonly")
        self.cb_usuario.pack(fill="x", pady=(2, 4))

        ttk.Label(card_csv, text="Columna Estado (Booleano):", style="Muted.TLabel").pack(anchor="w")
        self.cb_agregado = ttk.Combobox(card_csv, textvariable=self.col_agregado_var, state="readonly")
        self.cb_agregado.pack(fill="x", pady=(2, 6))

        row_umbral = ttk.Frame(card_csv, style="Panel.TFrame")
        row_umbral.pack(fill="x", pady=(0, 6))
        ttk.Label(row_umbral, text="Umbral similitud (0.5 - 1.0):", style="Muted.TLabel").pack(side="left")
        ttk.Spinbox(
            row_umbral, from_=0.50, to=1.00, increment=0.05, textvariable=self.umbral_var, width=7, format="%.2f"
        ).pack(side="right")

        self.btn_cargar = ttk.Button(
            card_csv, text="Cargar y Analizar CSV", style="Primary.TButton", command=self._cargar_y_analizar_csv
        )
        self.btn_cargar.pack(fill="x")

        # 2. Credenciales GitHub
        card_gh = ttk.LabelFrame(inner, text="2. Configuración GitHub (.env)", style="Card.TLabelframe")
        card_gh.pack(fill="x", pady=(0, 4), padx=(0, 4))

        ttk.Label(card_gh, text="GitHub Token:", style="Muted.TLabel").pack(anchor="w")
        ttk.Entry(card_gh, textvariable=self.token_var, show="*").pack(fill="x", pady=(2, 4))

        ttk.Label(card_gh, text="Colaborador por defecto (opcional):", style="Muted.TLabel").pack(anchor="w")
        ttk.Entry(card_gh, textvariable=self.colaborador_defecto_var).pack(fill="x", pady=(2, 4))

        ttk.Label(card_gh, text="Organización (dejar vacío si es cuenta personal):", style="Muted.TLabel").pack(anchor="w")
        ttk.Entry(card_gh, textvariable=self.org_var).pack(fill="x", pady=(2, 4))

        row_pausa = ttk.Frame(card_gh, style="Panel.TFrame")
        row_pausa.pack(fill="x", pady=(2, 4))
        ttk.Label(row_pausa, text="Pausa entre grupos (seg):", style="Muted.TLabel").pack(side="left")
        ttk.Spinbox(row_pausa, from_=2, to=60, increment=1, textvariable=self.pausa_grupos_var, width=7).pack(side="right")

        ttk.Checkbutton(
            card_gh,
            text="Agregar a repos existentes sin preguntar",
            variable=self.auto_existentes_var,
            style="Panel.TCheckbutton",
        ).pack(anchor="w", pady=(2, 0))

    def _construir_panel_derecho(self, parent: ttk.Frame) -> None:
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill="both", expand=True)

        # Pestaña 1: Grupos y Pendientes
        self.tab_grupos = ttk.Frame(self.notebook, style="Panel.TFrame", padding=10)
        self.notebook.add(self.tab_grupos, text="Grupos y Pendientes")

        cols_grupos = ("grupo", "slug", "pendientes", "usuarios", "estado")
        self.tree_grupos = ttk.Treeview(self.tab_grupos, columns=cols_grupos, show="headings")
        self.tree_grupos.heading("grupo", text="Grupo (limpio)")
        self.tree_grupos.heading("slug", text="Repositorio GitHub")
        self.tree_grupos.heading("pendientes", text="Pendientes")
        self.tree_grupos.heading("usuarios", text="Usuarios por agregar")
        self.tree_grupos.heading("estado", text="Estado")

        self.tree_grupos.column("grupo", width=180)
        self.tree_grupos.column("slug", width=180)
        self.tree_grupos.column("pendientes", width=85, anchor="center")
        self.tree_grupos.column("usuarios", width=230)
        self.tree_grupos.column("estado", width=120, anchor="center")

        sb_g = ttk.Scrollbar(self.tab_grupos, orient="vertical", command=self.tree_grupos.yview)
        self.tree_grupos.configure(yscrollcommand=sb_g.set)
        self.tree_grupos.pack(side="left", fill="both", expand=True)
        sb_g.pack(side="right", fill="y")

        # Franja de métricas y exportación debajo del notebook
        metrics_bar = ttk.Frame(parent, style="Panel.TFrame", padding=(10, 6))
        metrics_bar.pack(fill="x", pady=(8, 0))
        ttk.Label(metrics_bar, textvariable=self.metricas_var, style="Muted.TLabel").pack(side="left")

        self.btn_resumen = ttk.Button(
            metrics_bar,
            text="Exportar Resumen con Links",
            style="Secondary.TButton",
            command=self._exportar_resumen,
        )
        self.btn_resumen.pack(side="right")

        # Pestaña 2: Unificar Categorías
        self.tab_unificar = ttk.Frame(self.notebook, style="Panel.TFrame", padding=10)
        self.notebook.add(self.tab_unificar, text="Unificar Categorías (0)")

        ttk.Label(
            self.tab_unificar,
            text="Selecciona un par detectado, elige qué nombre conservar y pulsa 'Aplicar Unificaciones'.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 8))

        frame_tree_u = ttk.Frame(self.tab_unificar, style="Panel.TFrame")
        frame_tree_u.pack(fill="both", expand=True)

        cols_u = ("op1", "op2", "sim", "decision")
        self.tree_unificar = ttk.Treeview(frame_tree_u, columns=cols_u, show="headings", selectmode="browse")
        self.tree_unificar.heading("op1", text="Opción [1] (más frecuente)")
        self.tree_unificar.heading("op2", text="Opción [2]")
        self.tree_unificar.heading("sim", text="Similitud")
        self.tree_unificar.heading("decision", text="Decisión")

        self.tree_unificar.column("op1", width=240)
        self.tree_unificar.column("op2", width=240)
        self.tree_unificar.column("sim", width=85, anchor="center")
        self.tree_unificar.column("decision", width=190, anchor="center")

        sb_u = ttk.Scrollbar(frame_tree_u, orient="vertical", command=self.tree_unificar.yview)
        self.tree_unificar.configure(yscrollcommand=sb_u.set)
        self.tree_unificar.pack(side="left", fill="both", expand=True)
        sb_u.pack(side="right", fill="y")

        btns_u = ttk.Frame(self.tab_unificar, style="Panel.TFrame", padding=(0, 10, 0, 0))
        btns_u.pack(fill="x")

        ttk.Button(
            btns_u, text="Conservar [1]", style="Secondary.TButton", command=lambda: self._decidir_par("1")
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            btns_u, text="Conservar [2]", style="Secondary.TButton", command=lambda: self._decidir_par("2")
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            btns_u, text="Mantener ambas", style="Secondary.TButton", command=lambda: self._decidir_par("ambas")
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            btns_u, text="Auto [1] a todas", style="Secondary.TButton", command=self._decidir_todas_op1
        ).pack(side="left")

        ttk.Button(
            btns_u, text="Aplicar Unificaciones", style="Primary.TButton", command=self._aplicar_unificaciones
        ).pack(side="right")

        # Pestaña 3: Usuarios Inválidos
        self.tab_invalidos = ttk.Frame(self.notebook, style="Panel.TFrame", padding=10)
        self.notebook.add(self.tab_invalidos, text="Usuarios Inválidos (0)")

        cols_inv = ("grupo", "valor")
        self.tree_invalidos = ttk.Treeview(self.tab_invalidos, columns=cols_inv, show="headings")
        self.tree_invalidos.heading("grupo", text="Grupo")
        self.tree_invalidos.heading("valor", text="Valor inválido detectado en el CSV")
        self.tree_invalidos.column("grupo", width=260)
        self.tree_invalidos.column("valor", width=480)

        sb_i = ttk.Scrollbar(self.tab_invalidos, orient="vertical", command=self.tree_invalidos.yview)
        self.tree_invalidos.configure(yscrollcommand=sb_i.set)
        self.tree_invalidos.pack(side="left", fill="both", expand=True)
        sb_i.pack(side="right", fill="y")

        # Pestaña 4: Consola de Actividad
        self.tab_logs = ttk.Frame(self.notebook, style="Panel.TFrame", padding=10)
        self.notebook.add(self.tab_logs, text="Consola de Actividad")

        top_log = ttk.Frame(self.tab_logs, style="Panel.TFrame")
        top_log.pack(fill="x", pady=(0, 6))
        ttk.Label(top_log, text="Salida detallada de operaciones y API de GitHub:", style="Muted.TLabel").pack(side="left")
        ttk.Button(top_log, text="Limpiar consola", style="Secondary.TButton", command=self._limpiar_logs).pack(side="right")

        frame_txt = ttk.Frame(self.tab_logs, style="Panel.TFrame")
        frame_txt.pack(fill="both", expand=True)

        self.txt_logs = tk.Text(
            frame_txt,
            bg=BG_INPUT,
            fg=FG_TEXT,
            font=("Consolas", 9),
            relief="flat",
            wrap="word",
            state="disabled",
            padx=8,
            pady=8,
        )
        sb_l = ttk.Scrollbar(frame_txt, orient="vertical", command=self.txt_logs.yview)
        self.txt_logs.configure(yscrollcommand=sb_l.set)
        self.txt_logs.pack(side="left", fill="both", expand=True)
        sb_l.pack(side="right", fill="y")

        self.txt_logs.tag_config("ok", foreground=SUCCESS)
        self.txt_logs.tag_config("invite", foreground="#38BDF8")
        self.txt_logs.tag_config("warn", foreground=WARNING)
        self.txt_logs.tag_config("error", foreground=DANGER)
        self.txt_logs.tag_config("muted", foreground=FG_MUTED)
        self.txt_logs.tag_config("header", foreground="#A78BFA", font=("Consolas", 9, "bold"))

    # ------------------------------------------------------------------
    # Logging seguro entre hilos
    # ------------------------------------------------------------------
    def _log(self, mensaje: str) -> None:
        self.log_queue.put(mensaje)

    def _procesar_cola_logs(self) -> None:
        while not self.log_queue.empty():
            msg = self.log_queue.get_nowait()
            tag = None
            upper = msg.upper()
            if "[ERROR]" in upper:
                tag = "error"
            elif "[CREADO]" in upper or "[OK]" in upper or "[LISTO]" in upper:
                tag = "ok"
            elif "[INVITADO]" in upper:
                tag = "invite"
            elif "[AVISO]" in upper or "[RATE LIMIT]" in upper or "[DETENIDO]" in upper:
                tag = "warn"
            elif "[YA EXISTÍA]" in upper or "[OMITIDO]" in upper:
                tag = "muted"
            elif msg.strip().startswith("---") or msg.strip().startswith("==="):
                tag = "header"

            self.txt_logs.configure(state="normal")
            self.txt_logs.insert("end", msg + "\n", tag)
            self.txt_logs.see("end")
            self.txt_logs.configure(state="disabled")

        self.after(100, self._procesar_cola_logs)

    def _limpiar_logs(self) -> None:
        self.txt_logs.configure(state="normal")
        self.txt_logs.delete("1.0", "end")
        self.txt_logs.configure(state="disabled")

    # ------------------------------------------------------------------
    # Carga de CSV, limpieza, unificación y exportación de resumen
    # ------------------------------------------------------------------
    def _seleccionar_csv(self) -> None:
        ruta = filedialog.askopenfilename(
            title="Seleccionar archivo CSV",
            filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")],
        )
        if ruta:
            self.ruta_csv_var.set(ruta)
            self._cargar_encabezados_csv(ruta)

    def _cargar_encabezados_csv(self, ruta: str) -> None:
        try:
            cols = list(pd.read_csv(ruta, nrows=0).columns)
        except Exception as exc:
            messagebox.showerror("Error al leer CSV", f"No se pudieron leer las columnas:\n{exc}")
            return

        for cb in (self.cb_grupo, self.cb_usuario, self.cb_agregado):
            cb["values"] = cols

        if self.col_grupo_var.get() not in cols and cols:
            self.col_grupo_var.set(cols[0])
        if self.col_usuario_var.get() not in cols and len(cols) > 1:
            self.col_usuario_var.set(cols[1])
        if self.col_agregado_var.get() not in cols and len(cols) > 2:
            self.col_agregado_var.set(cols[-1])

    def _cargar_y_analizar_csv(self) -> None:
        ruta = self.ruta_csv_var.get().strip()
        if not ruta or not os.path.exists(ruta):
            messagebox.showwarning("CSV no encontrado", "Selecciona un archivo CSV válido primero.")
            return

        col_g = self.col_grupo_var.get()
        col_u = self.col_usuario_var.get()
        col_a = self.col_agregado_var.get()

        try:
            df_raw = pd.read_csv(ruta)
            for col in (col_g, col_u, col_a):
                if col not in df_raw.columns:
                    raise ValueError(f"La columna '{col}' no existe en el archivo.")

            self.df_groups = fd.modification_groups(df_raw, col_g)
            self._recalcular_vistas()
            self._log(f"[LISTO] CSV cargado y normalizado: '{os.path.basename(ruta)}' ({len(self.df_groups)} filas).")

            if self.pares_similares:
                self.notebook.select(self.tab_unificar)
                self._log(
                    f"[AVISO] Se detectaron {len(self.pares_similares)} par(es) de grupos similares. "
                    "Revísalos en la pestaña 'Unificar Categorías'."
                )
            else:
                self.notebook.select(self.tab_grupos)

        except Exception as exc:
            messagebox.showerror("Error procesando CSV", str(exc))
            self._log(f"[ERROR] Al analizar CSV: {exc}")

    def _recalcular_vistas(self) -> None:
        if self.df_groups is None:
            return

        col_g = self.col_grupo_var.get()
        col_u = self.col_usuario_var.get()
        col_a = self.col_agregado_var.get()
        umbral = float(self.umbral_var.get())

        # 1. Grupos y usuarios inválidos
        self.invalidos = []
        self.grupos_github = fd.agrupar_usuarios_por_grupo(
            self.df_groups,
            col_grupo=col_g,
            col_usuario=col_u,
            col_agregado=col_a,
            incluir_grupos_vacios=True,
            on_log=self._log,
            invalidos_out=self.invalidos,
        )

        # Tabla Grupos
        self.tree_grupos.delete(*self.tree_grupos.get_children())
        total_pendientes = 0
        for grupo, usuarios in self.grupos_github.items():
            slug = gm.formatear_nombre_repo(str(grupo))
            cant = len(usuarios)
            total_pendientes += cant
            estado = "Al día" if cant == 0 else "Pendiente"
            lista_str = ", ".join(usuarios) if usuarios else "—"
            self.tree_grupos.insert("", "end", iid=grupo, values=(grupo, slug, cant, lista_str, estado))

        # Tabla Inválidos
        self.tree_invalidos.delete(*self.tree_invalidos.get_children())
        for grupo_inv, val_inv in self.invalidos:
            self.tree_invalidos.insert("", "end", values=(grupo_inv, val_inv))
        self.notebook.tab(self.tab_invalidos, text=f"Usuarios Inválidos ({len(self.invalidos)})")

        # 2. Pares similares
        pares = fd.detectar_pares_similares(self.df_groups, col_g, umbral=umbral)
        self.pares_similares = [
            {"op1": a, "op2": b, "sim": sim, "decision": "ambas"} for a, b, sim in pares
        ]
        self._refrescar_tabla_unificar()

        # Métricas
        self.metricas_var.set(
            f"Filas: {len(self.df_groups)}  |  Grupos: {len(self.grupos_github)}  |  "
            f"Pendientes: {total_pendientes}  |  Inválidos: {len(self.invalidos)}"
        )

    def _refrescar_tabla_unificar(self) -> None:
        self.tree_unificar.delete(*self.tree_unificar.get_children())
        etiquetas = {"1": "Conservar [1]", "2": "Conservar [2]", "ambas": "Mantener ambas"}

        for idx, item in enumerate(self.pares_similares):
            self.tree_unificar.insert(
                "",
                "end",
                iid=str(idx),
                values=(item["op1"], item["op2"], f"{item['sim'] * 100:.0f}%", etiquetas[item["decision"]]),
            )
        self.notebook.tab(self.tab_unificar, text=f"Unificar Categorías ({len(self.pares_similares)})")

    def _decidir_par(self, decision: str) -> None:
        seleccion = self.tree_unificar.selection()
        if not seleccion:
            return
        idx = int(seleccion[0])
        self.pares_similares[idx]["decision"] = decision
        self._refrescar_tabla_unificar()
        if idx + 1 < len(self.pares_similares):
            self.tree_unificar.selection_set(str(idx + 1))

    def _decidir_todas_op1(self) -> None:
        for item in self.pares_similares:
            item["decision"] = "1"
        self._refrescar_tabla_unificar()

    def _aplicar_unificaciones(self) -> None:
        if self.df_groups is None:
            return

        reemplazos: dict[str, str] = {}
        for item in self.pares_similares:
            if item["decision"] == "1":
                reemplazos[item["op2"]] = item["op1"]
            elif item["decision"] == "2":
                reemplazos[item["op1"]] = item["op2"]

        if not reemplazos:
            messagebox.showinfo("Sin cambios", "No hay unificaciones marcadas para aplicar.")
            return

        self.df_groups = fd.aplicar_reemplazos_categorias(
            self.df_groups, self.col_grupo_var.get(), reemplazos
        )
        self._log(f"[OK] Se unificaron {len(reemplazos)} categoría(s) en memoria.")
        self._recalcular_vistas()
        self.notebook.select(self.tab_grupos)

    def _exportar_resumen(self) -> None:
        if self.df_groups is None:
            messagebox.showwarning("Sin datos", "Primero carga y analiza el archivo CSV.")
            return

        owner = self.owner_actual or self.org_var.get().strip()
        if not owner:
            token = self.token_var.get().strip()
            if not token:
                messagebox.showwarning(
                    "Falta cuenta de GitHub",
                    "Configura GITHUB_TOKEN (o la Organización) y verifica la conexión para construir los enlaces.",
                )
                return
            try:
                headers = gm.construir_headers(token)
                owner = gm.obtener_owner(headers, org=None)
                self.owner_actual = owner
                self.status_conexion_var.set(f"Conectado: {owner}")
                self.lbl_conexion.configure(foreground=SUCCESS)
            except Exception as exc:
                messagebox.showerror(
                    "Error de conexión",
                    f"No se pudo obtener el usuario dueño de los repositorios:\n{exc}",
                )
                return

        ruta_salida = filedialog.asksaveasfilename(
            title="Guardar resumen de integrantes y enlaces",
            initialfile="resumen_repositorios",
            defaultextension=".md",
            filetypes=[
                ("Markdown con enlaces clickeables (*.md)", "*.md"),
                ("Archivo CSV para Excel (*.csv)", "*.csv"),
            ],
        )
        if not ruta_salida:
            return

        try:
            resumen = fd.generar_resumen_integrantes(
                df=self.df_groups,
                col_grupo=self.col_grupo_var.get(),
                col_usuario=self.col_usuario_var.get(),
                col_agregado=self.col_agregado_var.get(),
                owner=owner,
                formatear_slug_fn=gm.formatear_nombre_repo,
            )
            fd.exportar_resumen_integrantes(resumen, ruta_salida)
            self._log(f"[LISTO] Resumen exportado con {len(resumen)} grupo(s) en: '{ruta_salida}'")
            messagebox.showinfo(
                "Resumen exportado",
                f"Se guardó el resumen con los enlaces de {len(resumen)} grupo(s) en:\n{ruta_salida}",
            )
        except Exception as exc:
            self._log(f"[ERROR] No se pudo exportar el resumen: {exc}")
            messagebox.showerror("Error al exportar", str(exc))

    # ------------------------------------------------------------------
    # Conexión y ejecución en segundo plano (GitHub API)
    # ------------------------------------------------------------------
    def _verificar_conexion(self) -> None:
        token = self.token_var.get().strip()
        org = self.org_var.get().strip() or None
        if not token:
            messagebox.showwarning("Falta token", "Configura GITHUB_TOKEN en el archivo .env o en el campo Token.")
            return

        def _worker():
            try:
                headers = gm.construir_headers(token)
                owner = gm.obtener_owner(headers, org=org)
                self.owner_actual = owner
                self.after(0, lambda: self.status_conexion_var.set(f"Conectado: {owner}"))
                self.after(0, lambda: self.lbl_conexion.configure(foreground=SUCCESS))
                self._log(f"[OK] Autenticado en GitHub como: {owner}")
            except Exception as exc:
                self.owner_actual = None
                self.after(0, lambda: self.status_conexion_var.set("Error de conexión"))
                self.after(0, lambda: self.lbl_conexion.configure(foreground=DANGER))
                self._log(f"[ERROR] Falló la autenticación con GitHub: {exc}")

        threading.Thread(target=_worker, daemon=True).start()

    def _set_estado_ejecucion(self, activo: bool) -> None:
        self.en_ejecucion = activo
        estado_controles = "disabled" if activo else "normal"
        self.btn_cargar.configure(state=estado_controles)
        self.btn_ejecutar.configure(state=estado_controles)
        self.btn_defecto.configure(state=estado_controles)
        self.btn_verificar.configure(state=estado_controles)
        self.btn_resumen.configure(state=estado_controles)
        self.btn_detener.configure(state="normal" if activo else "disabled")

    def _confirmar_repo_existente_gui(self, owner: str, repo_slug: str) -> bool:
        if self.auto_existentes_var.get():
            return True

        respuesta = {"aceptar": False}
        evento = threading.Event()

        def _mostrar_dialogo():
            respuesta["aceptar"] = messagebox.askyesno(
                "Repositorio existente",
                f"El repositorio '{owner}/{repo_slug}' ya existe en GitHub.\n\n"
                "¿Deseas agregar los usuarios pendientes a este repositorio?",
            )
            evento.set()

        self.after(0, _mostrar_dialogo)
        evento.wait()
        return respuesta["aceptar"]

    def _actualizar_fila_grupo(self, grupo: str, estado: str, pendientes_restantes: list[str] | None = None) -> None:
        if not self.tree_grupos.exists(grupo):
            return
        vals = list(self.tree_grupos.item(grupo, "values"))
        vals[4] = estado
        if pendientes_restantes is not None:
            vals[2] = len(pendientes_restantes)
            vals[3] = ", ".join(pendientes_restantes) if pendientes_restantes else "—"
        self.tree_grupos.item(grupo, values=vals)

    def _iniciar_procesamiento_repos(self) -> None:
        if self.df_groups is None:
            messagebox.showwarning("Sin datos", "Primero carga y analiza el archivo CSV.")
            return

        token = self.token_var.get().strip()
        if not token:
            messagebox.showwarning("Falta token", "Ingresa o configura GITHUB_TOKEN antes de continuar.")
            return

        pendientes_por_grupo = {g: u for g, u in self.grupos_github.items() if u}
        if not pendientes_por_grupo:
            messagebox.showinfo("Nada pendiente", "Todos los usuarios válidos ya están marcados como True.")
            return

        self.stop_event.clear()
        self._set_estado_ejecucion(True)
        self.notebook.select(self.tab_logs)

        ruta_csv = self.ruta_csv_var.get().strip()
        col_g = self.col_grupo_var.get()
        col_u = self.col_usuario_var.get()
        col_a = self.col_agregado_var.get()
        org = self.org_var.get().strip() or None
        colab_def = self.colaborador_defecto_var.get().strip() or None
        pausa_grupos = int(self.pausa_grupos_var.get())

        def _worker():
            try:
                headers = gm.construir_headers(token)
                owner = gm.obtener_owner(headers, org=org)
                self.owner_actual = owner
                self.after(0, lambda: self.status_conexion_var.set(f"Conectado: {owner}"))
                self.after(0, lambda: self.lbl_conexion.configure(foreground=SUCCESS))
                self._log(f"[OK] Autenticado en GitHub como: {owner}")

                total = len(pendientes_por_grupo)
                self.after(0, lambda: self.progress.configure(maximum=total, value=0))

                for idx, (grupo, usuarios) in enumerate(pendientes_por_grupo.items(), start=1):
                    if self.stop_event.is_set():
                        self._log("[DETENIDO] Proceso cancelado por el usuario.")
                        break

                    self.after(0, lambda g=grupo: self._actualizar_fila_grupo(g, "Procesando..."))
                    self.after(0, lambda i=idx, t=total, g=grupo: self.status_progreso_var.set(
                        f"Procesando grupo {i}/{t}: {g}"
                    ))

                    exitosos = gm.procesar_grupo_en_github(
                        nombre_grupo=grupo,
                        usuarios=usuarios,
                        owner=owner,
                        headers=headers,
                        colaborador_defecto=colab_def,
                        org=org,
                        on_log=self._log,
                        on_repo_existente=self._confirmar_repo_existente_gui,
                        stop_event=self.stop_event,
                    )

                    for usuario in exitosos:
                        self.df_groups = fd.actualizar_estado_usuario(
                            self.df_groups,
                            grupo=grupo,
                            usuario=usuario,
                            col_grupo=col_g,
                            col_usuario=col_u,
                            col_agregado=col_a,
                        )

                    # Guarda avance inmediatamente tras cada grupo
                    fd.reemplazar_csv(self.df_groups, ruta_csv)

                    restantes = [u for u in usuarios if u not in exitosos]
                    estado_final = (
                        "Completado"
                        if not restantes
                        else (f"Parcial ({len(exitosos)}/{len(usuarios)})" if exitosos else "Omitido / Error")
                    )
                    self.after(0, lambda g=grupo, e=estado_final, r=restantes: self._actualizar_fila_grupo(g, e, r))
                    self.after(0, lambda i=idx: self.progress.configure(value=i))

                    if idx < total and not self.stop_event.is_set():
                        self._log(f"  Esperando {pausa_grupos}s antes del siguiente grupo...")
                        self.stop_event.wait(timeout=pausa_grupos)

            except Exception as exc:
                self._log(f"[ERROR] Fallo inesperado durante la ejecución: {exc}")
            finally:
                if self.df_groups is not None and ruta_csv:
                    try:
                        fd.reemplazar_csv(self.df_groups, ruta_csv)
                        self._log(f"\n[LISTO] Archivo '{ruta_csv}' actualizado con el DataFrame final.")
                    except Exception as exc:
                        self._log(f"[ERROR] No se pudo guardar '{ruta_csv}' (¿está abierto en Excel?): {exc}")

                self.after(0, self._recalcular_vistas)
                self.after(0, lambda: self.status_progreso_var.set("Proceso finalizado."))
                self.after(0, lambda: self._set_estado_ejecucion(False))

        threading.Thread(target=_worker, daemon=True).start()

    def _iniciar_solo_defecto(self) -> None:
        if self.df_groups is None:
            messagebox.showwarning("Sin datos", "Primero carga y analiza el archivo CSV.")
            return

        token = self.token_var.get().strip()
        colab_def = self.colaborador_defecto_var.get().strip()
        if not token or not colab_def:
            messagebox.showwarning(
                "Datos faltantes", "Necesitas configurar el GitHub Token y el Colaborador por defecto."
            )
            return

        self.stop_event.clear()
        self._set_estado_ejecucion(True)
        self.notebook.select(self.tab_logs)

        col_g = self.col_grupo_var.get()
        org = self.org_var.get().strip() or None

        def _worker():
            try:
                headers = gm.construir_headers(token)
                owner = gm.obtener_owner(headers, org=org)
                self.after(0, lambda: self.status_conexion_var.set(f"Conectado: {owner}"))
                self.after(0, lambda: self.lbl_conexion.configure(foreground=SUCCESS))

                def _progreso(actual: int, total: int, texto: str):
                    self.after(0, lambda: self.progress.configure(maximum=total, value=actual))
                    self.after(0, lambda: self.status_progreso_var.set(f"({actual}/{total}) {texto}"))

                gm.asignar_colaborador_defecto_a_todos(
                    df=self.df_groups,
                    col_grupo=col_g,
                    owner=owner,
                    headers=headers,
                    colaborador_defecto=colab_def,
                    org=org,
                    pausa_segundos=4,
                    on_log=self._log,
                    on_progreso=_progreso,
                    stop_event=self.stop_event,
                )
            except Exception as exc:
                self._log(f"[ERROR] En asignación por defecto: {exc}")
            finally:
                self.after(0, lambda: self.status_progreso_var.set("Asignación finalizada."))
                self.after(0, lambda: self._set_estado_ejecucion(False))

        threading.Thread(target=_worker, daemon=True).start()

    def _detener_proceso(self) -> None:
        if self.en_ejecucion:
            self.stop_event.set()
            self.status_progreso_var.set("Deteniendo y guardando progreso...")
            self._log("[AVISO] Solicitando detención segura...")

    def _al_cerrar(self) -> None:
        if self.en_ejecucion:
            if not messagebox.askyesno(
                "Proceso en ejecución",
                "Hay operaciones activas en GitHub. ¿Deseas detener y cerrar la ventana?",
            ):
                return
            self.stop_event.set()
        self.destroy()


if __name__ == "__main__":
    app = RepCreatorApp()
    app.mainloop()