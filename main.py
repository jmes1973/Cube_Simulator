import json
import os
import traceback

import customtkinter as ctk
import cv2
import numpy as np
from tkinter import filedialog, messagebox

from cube_processing import (
    app_log_path,
    apply_anonymization,
    export_pseudo4d_clips,
    get_logger,
    process_to_nrrd,
    read_middle_frame,
    to_uint8_for_display,
)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

MODE_PSEUDO_3D = "Pseudo 3D"
MODE_PSEUDO_4D = "Pseudo 4D"


def appdata_config_path():
    appdata = os.environ.get("APPDATA")
    cfg_dir = os.path.join(appdata, "Cube_Simulator")
    os.makedirs(cfg_dir, exist_ok=True)
    return os.path.join(cfg_dir, "config.json")


def load_config():
    cfg_path = appdata_config_path()
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(cfg: dict):
    cfg_path = appdata_config_path()
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def default_workspace_dir():
    local = os.environ.get("LOCALAPPDATA")
    return os.path.join(local, "Cube_Simulator_Workspace")


def ensure_workspace_dirs(workspace_dir: str):
    data_dir = os.path.join(workspace_dir, "data_source")
    out_dir = os.path.join(workspace_dir, "output_volumes")
    presets = os.path.join(workspace_dir, "presets")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(presets, exist_ok=True)
    return data_dir, out_dir, presets


class CubeSimulator(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.logger = get_logger()
        self.cfg = load_config()
        self.title("Cube_Simulator - Pseudo 3D / Pseudo 4D")
        self.geometry("900x800")

        self.video_actual = None
        self.crop_roi = None
        self.mask_rects = []
        self.mask_mode = self.cfg.get("mask_mode", "black")
        self.output_mode_var = ctk.StringVar(value=self.cfg.get("output_mode", MODE_PSEUDO_3D))
        self.p4d_motion_var = ctk.StringVar(value=self.cfg.get("p4d_motion", "Abanico"))
        self.p4d_sweep_cm_var = ctk.StringVar(value=str(self.cfg.get("p4d_sweep_cm", "2.0")))
        self.p4d_z_slices_var = ctk.StringVar(value=str(self.cfg.get("p4d_z_slices", "40")))
        self.p4d_fan_angle_var = ctk.StringVar(value=str(self.cfg.get("p4d_fan_angle_deg", "12")))

        self.label_titulo = ctk.CTkLabel(self, text="CUBE SIMULATOR", font=("Roboto", 28, "bold"))
        self.label_titulo.pack(pady=(18, 8))

        self.mode_frame = ctk.CTkFrame(self)
        self.mode_frame.pack(padx=18, pady=6, fill="x")

        self.mode_title = ctk.CTkLabel(self.mode_frame, text="Modo de salida", font=("Roboto", 18, "bold"))
        self.mode_title.pack(anchor="w", padx=14, pady=(12, 4))

        self.mode_switch = ctk.CTkSegmentedButton(
            self.mode_frame,
            values=[MODE_PSEUDO_3D, MODE_PSEUDO_4D],
            variable=self.output_mode_var,
            command=self._on_mode_change,
        )
        self.mode_switch.pack(anchor="w", padx=14, pady=6)

        self.mode_hint = ctk.CTkLabel(self.mode_frame, text="", text_color="gray", justify="left")
        self.mode_hint.pack(anchor="w", padx=14, pady=(2, 12))

        self.p4d_frame = ctk.CTkFrame(self.mode_frame)
        self.p4d_frame.pack(fill="x", padx=12, pady=(0, 12))

        self.p4d_title = ctk.CTkLabel(self.p4d_frame, text="Parametros de Pseudo 4D", font=("Roboto", 16, "bold"))
        self.p4d_title.grid(row=0, column=0, columnspan=4, sticky="w", padx=12, pady=(10, 6))

        self.p4d_motion_label = ctk.CTkLabel(self.p4d_frame, text="Movimiento sintetico")
        self.p4d_motion_label.grid(row=1, column=0, sticky="w", padx=12, pady=6)
        self.p4d_motion = ctk.CTkSegmentedButton(self.p4d_frame, values=["Abanico", "Lineal"], variable=self.p4d_motion_var, command=lambda _: self._save_preferences())
        self.p4d_motion.grid(row=1, column=1, columnspan=3, sticky="ew", padx=12, pady=6)

        self.p4d_sweep_label = ctk.CTkLabel(self.p4d_frame, text="Barrido simulado (cm)")
        self.p4d_sweep_label.grid(row=2, column=0, sticky="w", padx=12, pady=6)
        self.p4d_sweep_entry = ctk.CTkEntry(self.p4d_frame, textvariable=self.p4d_sweep_cm_var, width=120)
        self.p4d_sweep_entry.grid(row=2, column=1, sticky="w", padx=12, pady=6)

        self.p4d_z_label = ctk.CTkLabel(self.p4d_frame, text="Posiciones en Z")
        self.p4d_z_label.grid(row=2, column=2, sticky="w", padx=12, pady=6)
        self.p4d_z_entry = ctk.CTkEntry(self.p4d_frame, textvariable=self.p4d_z_slices_var, width=120)
        self.p4d_z_entry.grid(row=2, column=3, sticky="w", padx=12, pady=6)

        self.p4d_angle_label = ctk.CTkLabel(self.p4d_frame, text="Apertura abanico (+/- grados)")
        self.p4d_angle_label.grid(row=3, column=0, sticky="w", padx=12, pady=6)
        self.p4d_angle_entry = ctk.CTkEntry(self.p4d_frame, textvariable=self.p4d_fan_angle_var, width=120)
        self.p4d_angle_entry.grid(row=3, column=1, sticky="w", padx=12, pady=6)

        self.p4d_note = ctk.CTkLabel(
            self.p4d_frame,
            text="Paso actual: Pseudo 4D conserva el movimiento temporal del video base y crea clips por posicion Z.",
            text_color="gray",
            justify="left",
            wraplength=760,
        )
        self.p4d_note.grid(row=4, column=0, columnspan=4, sticky="w", padx=12, pady=(4, 12))

        self.status_label = ctk.CTkLabel(self, text="Inicializando...", text_color="gray")
        self.status_label.pack(pady=4)

        self.workspace_frame = ctk.CTkFrame(self)
        self.workspace_frame.pack(padx=18, pady=6, fill="x")
        self.btn_change_workspace = ctk.CTkButton(self.workspace_frame, text="Cambiar workspace", command=self.cambiar_workspace, fg_color="#3F6AA2")
        self.btn_change_workspace.pack(side="left", padx=8, pady=10)
        self.btn_open_output = ctk.CTkButton(self.workspace_frame, text="Abrir carpeta de salida", command=self.abrir_carpeta_salida, fg_color="#2F7D4A")
        self.btn_open_output.pack(side="left", padx=8, pady=10)

        self.btn_cargar = ctk.CTkButton(self, text="1. CARGAR MP4 / AVI / DICOM", command=self.seleccionar_archivo)
        self.btn_cargar.pack(pady=10)

        self.frame_tools = ctk.CTkFrame(self)
        self.frame_tools.pack(pady=6, fill="x", padx=18)

        self.btn_roi = ctk.CTkButton(self.frame_tools, text="2. DEFINIR RECORTE (ROI)", command=self.definir_roi, state="disabled")
        self.btn_roi.pack(side="left", padx=8, pady=10)

        self.btn_masks = ctk.CTkButton(self.frame_tools, text="3. DEFINIR MASCARAS", command=self.definir_mascaras, state="disabled")
        self.btn_masks.pack(side="left", padx=8, pady=10)

        self.mask_mode_var = ctk.StringVar(value=self.mask_mode)
        self.opt_black = ctk.CTkRadioButton(
            self.frame_tools,
            text="Tapar (negro)",
            variable=self.mask_mode_var,
            value="black",
            command=self._update_mask_mode,
            state="disabled",
        )
        self.opt_black.pack(side="left", padx=10)

        self.opt_blur = ctk.CTkRadioButton(
            self.frame_tools,
            text="Difuminar",
            variable=self.mask_mode_var,
            value="blur",
            command=self._update_mask_mode,
            state="disabled",
        )
        self.opt_blur.pack(side="left", padx=10)

        self.btn_previa = ctk.CTkButton(self, text="4. PREVISUALIZAR RESULTADO", command=self.preview_resultado, state="disabled")
        self.btn_previa.pack(pady=10)

        self.btn_procesar = ctk.CTkButton(self, text="5. GENERAR PSEUDO 3D (.NRRD)", command=self.iniciar_proceso, state="disabled", fg_color="green")
        self.btn_procesar.pack(pady=10)

        self.btn_reset = ctk.CTkButton(self, text="Reiniciar ROI/Mascaras", command=self.reset_anon, state="disabled", fg_color="#444444")
        self.btn_reset.pack(pady=6)

        self.progressbar = ctk.CTkProgressBar(self, width=640)
        self.progressbar.set(0)
        self.progressbar.pack(pady=16)

        ok = self._init_workspace()
        if not ok:
            return

        self._bind_preference_events()
        self._on_mode_change(self.output_mode_var.get())
        self._refresh_status()

    def _bind_preference_events(self):
        for variable in [self.p4d_sweep_cm_var, self.p4d_z_slices_var, self.p4d_fan_angle_var]:
            variable.trace_add("write", lambda *_: self._save_preferences())

    def _refresh_status(self, extra_message: str | None = None):
        parts = [f"Workspace: {self.WORKSPACE_DIR}", f"Modo: {self.output_mode_var.get()}"]
        if self.video_actual:
            parts.insert(0, f"Cargado: {os.path.basename(self.video_actual)}")
        if extra_message:
            parts.append(extra_message)
        self.status_label.configure(text=" | ".join(parts), text_color="white")

    def _save_preferences(self):
        self.cfg["output_mode"] = self.output_mode_var.get()
        self.cfg["mask_mode"] = self.mask_mode_var.get()
        self.cfg["p4d_motion"] = self.p4d_motion_var.get()
        self.cfg["p4d_sweep_cm"] = self.p4d_sweep_cm_var.get()
        self.cfg["p4d_z_slices"] = self.p4d_z_slices_var.get()
        self.cfg["p4d_fan_angle_deg"] = self.p4d_fan_angle_var.get()
        if getattr(self, "WORKSPACE_DIR", None):
            self.cfg["workspace_dir"] = self.WORKSPACE_DIR
        save_config(self.cfg)

    def _open_folder(self, path: str):
        if not os.path.isdir(path):
            messagebox.showerror("Error", f"La carpeta no existe:\n{path}")
            return
        os.startfile(path)

    def cambiar_workspace(self):
        selected = filedialog.askdirectory(title="Selecciona una nueva carpeta de trabajo (Workspace)")
        if not selected:
            return
        try:
            self.DATA_DIR, self.OUT_DIR, self.PRESETS_DIR = ensure_workspace_dirs(selected)
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo usar la carpeta seleccionada:\n{exc}")
            return

        self.WORKSPACE_DIR = selected
        self._save_preferences()
        self._refresh_status("Workspace actualizado")

    def abrir_carpeta_salida(self):
        self._open_folder(self.OUT_DIR)

    def _init_workspace(self) -> bool:
        ws = self.cfg.get("workspace_dir")

        if (not ws) or (not os.path.isdir(ws)):
            suggested = default_workspace_dir()
            use_suggested = messagebox.askyesno(
                "Configurar carpeta de trabajo",
                "Esta aplicacion necesita una carpeta de trabajo para leer videos y guardar volumenes.\n\n"
                f"Ubicacion sugerida:\n{suggested}\n\n"
                "Quieres usar esta ubicacion?",
            )

            if use_suggested:
                ws = suggested
            else:
                ws = filedialog.askdirectory(title="Elige la carpeta de trabajo (Workspace)")
                if not ws:
                    messagebox.showerror("Cancelado", "No se selecciono carpeta de trabajo. La aplicacion se cerrara.")
                    self.destroy()
                    return False

            try:
                ensure_workspace_dirs(ws)
            except Exception as e:
                messagebox.showerror(
                    "Error creando carpetas",
                    f"No se pudo crear la estructura del workspace en:\n{ws}\n\nDetalle:\n{e}\n\n"
                    "Sugerencia: elige una carpeta distinta (por ejemplo C:\\Cube_Workspace o D:\\Cube_Workspace).",
                )
                ws2 = filedialog.askdirectory(title="Elige otra carpeta de trabajo (Workspace)")
                if not ws2:
                    self.destroy()
                    return False
                ws = ws2
                try:
                    ensure_workspace_dirs(ws)
                except Exception as e2:
                    messagebox.showerror("Error creando carpetas", f"Tampoco se pudo crear la estructura en:\n{ws}\n\nDetalle:\n{e2}")
                    self.destroy()
                    return False

        self.WORKSPACE_DIR = ws
        try:
            self.DATA_DIR, self.OUT_DIR, self.PRESETS_DIR = ensure_workspace_dirs(ws)
        except Exception as e:
            messagebox.showerror("Error creando carpetas", f"No se pudo crear la estructura del workspace en:\n{ws}\n\nDetalle:\n{e}")
            self.destroy()
            return False

        self._save_preferences()
        return True

    def _on_mode_change(self, selected_mode: str):
        if selected_mode == MODE_PSEUDO_4D:
            self.mode_hint.configure(
                text=(
                    "Pseudo 4D: conserva el AVI como base temporal y exporta micro clips por posicion Z.\n"
                    "Cada clip mantiene el movimiento original del video y solo cambia su posicion espacial sintetica."
                )
            )
            self.btn_procesar.configure(text="5. GENERAR PSEUDO 4D (CLIPS)")
            self._set_p4d_controls_state("normal")
        else:
            self.mode_hint.configure(
                text=(
                    "Pseudo 3D: usa el pipeline actual de volumen navegable. Convierte la secuencia cargada en un volumen .nrrd\n"
                    "y aplica compatibilidad automatica para OPUS cuando el caso es demasiado grande."
                )
            )
            self.btn_procesar.configure(text="5. GENERAR PSEUDO 3D (.NRRD)")
            self._set_p4d_controls_state("disabled")

        self._save_preferences()
        self._refresh_status()

    def _set_p4d_controls_state(self, state: str):
        widgets = [self.p4d_motion, self.p4d_sweep_entry, self.p4d_z_entry, self.p4d_angle_entry]
        for widget in widgets:
            widget.configure(state=state)

        text_color = "white" if state == "normal" else "gray"
        for label in [self.p4d_motion_label, self.p4d_sweep_label, self.p4d_z_label, self.p4d_angle_label]:
            label.configure(text_color=text_color)
        self.p4d_note.configure(text_color="gray")

    def _update_mask_mode(self):
        self.mask_mode = self.mask_mode_var.get()
        self._save_preferences()

    def reset_anon(self):
        self.crop_roi = None
        self.mask_rects = []
        self._refresh_status("Anonimizacion reiniciada")

    def _leer_frame_medio(self):
        if not self.video_actual:
            return None
        return read_middle_frame(self.video_actual)

    def _aplicar_anonimizacion(self, frame):
        return apply_anonymization(frame, self.crop_roi, self.mask_rects, self.mask_mode)

    def definir_roi(self):
        frame = self._leer_frame_medio()
        if frame is None:
            messagebox.showerror("Error", "No se pudo leer un frame para definir el recorte.")
            return

        disp = frame
        if len(disp.shape) == 2:
            disp = to_uint8_for_display(disp)
            disp = cv2.cvtColor(disp, cv2.COLOR_GRAY2BGR)
        elif disp.dtype != np.uint8:
            g = to_uint8_for_display(cv2.cvtColor(disp, cv2.COLOR_BGR2GRAY))
            disp = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)

        win = "Definir ROI (Enter=OK / C=Cancelar)"
        r = cv2.selectROI(win, disp, fromCenter=False, showCrosshair=True)
        cv2.destroyWindow(win)

        x, y, w, h = map(int, r)
        if w <= 0 or h <= 0:
            self.crop_roi = None
            self._refresh_status("ROI no definido")
            return

        self.crop_roi = (x, y, w, h)
        self.mask_rects = []
        self._refresh_status(f"ROI definido: x={x}, y={y}, w={w}, h={h}")

    def definir_mascaras(self):
        frame = self._leer_frame_medio()
        if frame is None:
            messagebox.showerror("Error", "No se pudo leer un frame para definir mascaras.")
            return

        frame_roi = frame.copy()
        if self.crop_roi is not None:
            x, y, w, h = self.crop_roi
            frame_roi = frame_roi[y:y + h, x:x + w]

        if frame_roi is None or frame_roi.size == 0:
            messagebox.showerror("Error", "El ROI definido deja el frame vacio. Ajusta el recorte e intenta de nuevo.")
            return

        if len(frame_roi.shape) == 2:
            base = to_uint8_for_display(frame_roi)
            canvas = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
        else:
            canvas = frame_roi.copy()
            if canvas.dtype != np.uint8:
                g = to_uint8_for_display(cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY))
                canvas = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)

        rects = []
        drawing = False
        x0, y0 = 0, 0

        def on_mouse(event, x, y, flags, param):
            nonlocal drawing, x0, y0, rects, canvas
            if event == cv2.EVENT_LBUTTONDOWN:
                drawing = True
                x0, y0 = x, y
            elif event == cv2.EVENT_MOUSEMOVE and drawing:
                tmp = canvas.copy()
                cv2.rectangle(tmp, (x0, y0), (x, y), (0, 255, 255), 2)
                for (a, b, c, d) in rects:
                    cv2.rectangle(tmp, (a, b), (c, d), (0, 255, 255), 2)
                cv2.imshow("Definir mascaras (Enter=OK / R=Reset / Esc=Salir)", tmp)
            elif event == cv2.EVENT_LBUTTONUP:
                drawing = False
                xa, xb = sorted([x0, x])
                ya, yb = sorted([y0, y])
                if (xb - xa) > 2 and (yb - ya) > 2:
                    rects.append((xa, ya, xb, yb))
                tmp = canvas.copy()
                for (a, b, c, d) in rects:
                    cv2.rectangle(tmp, (a, b), (c, d), (0, 255, 255), 2)
                cv2.imshow("Definir mascaras (Enter=OK / R=Reset / Esc=Salir)", tmp)

        win = "Definir mascaras (Enter=OK / R=Reset / Esc=Salir)"
        cv2.namedWindow(win)
        cv2.setMouseCallback(win, on_mouse)
        cv2.imshow(win, canvas)

        while True:
            k = cv2.waitKey(10) & 0xFF
            if k == 13:
                break
            if k == 27:
                rects = []
                break
            if k in (ord("r"), ord("R")):
                rects = []
                cv2.imshow(win, canvas)

        cv2.destroyWindow(win)

        self.mask_rects = rects
        if rects:
            self._refresh_status(f"Mascaras definidas: {len(rects)}")
        else:
            self._refresh_status("Mascaras no definidas")

    def preview_resultado(self):
        frame = self._leer_frame_medio()
        if frame is None:
            messagebox.showerror("Error", "No se pudo leer un frame para previsualizar.")
            return

        out = self._aplicar_anonimizacion(frame)
        if out is None:
            messagebox.showerror("Error", "El ROI definido deja el frame vacio. Ajusta el recorte e intenta de nuevo.")
            return

        if len(out.shape) == 2:
            disp = to_uint8_for_display(out)
        elif out.dtype != np.uint8:
            g = to_uint8_for_display(cv2.cvtColor(out, cv2.COLOR_BGR2GRAY))
            disp = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
        else:
            disp = out

        title = "Previsualizacion - Pseudo 4D" if self.output_mode_var.get() == MODE_PSEUDO_4D else "Previsualizacion - Pseudo 3D"
        cv2.imshow(title, disp)
        cv2.waitKey(0)
        cv2.destroyWindow(title)

    def seleccionar_archivo(self):
        try:
            self.attributes("-topmost", True)
            self.update_idletasks()
            path = filedialog.askopenfilename(
                parent=self,
                initialdir=self.DATA_DIR,
                title="Selecciona MP4 / AVI / DICOM",
                filetypes=[
                    ("Archivos Medicos", "*.mp4 *.avi *.dcm"),
                    ("DICOM", "*.dcm"),
                    ("Videos", "*.mp4 *.avi"),
                    ("Todos", "*.*"),
                ],
            )
        finally:
            try:
                self.attributes("-topmost", False)
            except Exception:
                pass

        self.video_actual = path

        if self.video_actual:
            self.btn_roi.configure(state="normal")
            self.btn_masks.configure(state="normal")
            self.opt_black.configure(state="normal")
            self.opt_blur.configure(state="normal")
            self.btn_previa.configure(state="normal")
            self.btn_procesar.configure(state="normal")
            self.btn_reset.configure(state="normal")
            self.crop_roi = None
            self.mask_rects = []
            self.progressbar.set(0)
            self._refresh_status("Archivo cargado")
        else:
            self._refresh_status()

    def _set_progress(self, value: float):
        self.progressbar.set(value)
        self.update_idletasks()

    def _get_pseudo4d_params(self):
        try:
            sweep_cm = float(self.p4d_sweep_cm_var.get())
            z_slices = int(self.p4d_z_slices_var.get())
            fan_angle_deg = float(self.p4d_fan_angle_var.get())
        except ValueError as exc:
            raise RuntimeError("Los parametros de Pseudo 4D deben ser numericos.") from exc

        if sweep_cm <= 0:
            raise RuntimeError("El barrido simulado debe ser mayor que 0 cm.")
        if z_slices < 2:
            raise RuntimeError("Pseudo 4D necesita al menos 2 posiciones en Z.")
        if fan_angle_deg < 0:
            raise RuntimeError("La apertura de abanico no puede ser negativa.")

        return {
            "motion_type": self.p4d_motion_var.get(),
            "sweep_cm": sweep_cm,
            "z_slices": z_slices,
            "fan_angle_deg": fan_angle_deg,
        }

    def iniciar_proceso(self):
        if not self.video_actual:
            messagebox.showwarning("Atencion", "Primero carga un archivo.")
            return

        nombre_base = os.path.basename(self.video_actual)
        base_sin_ext = os.path.splitext(nombre_base)[0]

        try:
            if self.output_mode_var.get() == MODE_PSEUDO_4D:
                params = self._get_pseudo4d_params()
                output_dir = os.path.join(self.OUT_DIR, base_sin_ext + "_pseudo4d")
                summary = export_pseudo4d_clips(
                    video_path=self.video_actual,
                    output_dir=output_dir,
                    crop_roi=self.crop_roi,
                    mask_rects=self.mask_rects,
                    mask_mode=self.mask_mode,
                    motion_type=params["motion_type"],
                    sweep_cm=params["sweep_cm"],
                    z_slices=params["z_slices"],
                    fan_angle_deg=params["fan_angle_deg"],
                    progress_callback=self._set_progress,
                )
                self.progressbar.set(1.0)
                lines = [
                    f"Pseudo 4D exportado correctamente:\n{summary.output_dir}",
                    "",
                    f"Manifest: {summary.manifest_path}",
                    f"Clips: {summary.clip_count}",
                    f"Frames por clip: {summary.frames_per_clip}",
                    f"FPS: {summary.fps:.2f}",
                    f"Tamano frame: {summary.frame_size[0]} x {summary.frame_size[1]}",
                    f"Movimiento: {summary.motion_type}",
                    f"Barrido simulado: {summary.sweep_cm} cm",
                    f"Apertura abanico: +/- {summary.fan_angle_deg} grados",
                ]
                messagebox.showinfo("Exito", "\n".join(lines))
                self._refresh_status(f"Exportado: {os.path.basename(summary.output_dir)}")
                return

            output_path = os.path.join(self.OUT_DIR, base_sin_ext + ".nrrd")
            summary = process_to_nrrd(
                video_path=self.video_actual,
                output_path=output_path,
                crop_roi=self.crop_roi,
                mask_rects=self.mask_rects,
                mask_mode=self.mask_mode,
                progress_callback=self._set_progress,
            )
            self.progressbar.set(1.0)

            lines = [
                f"NRRD creado correctamente:\n{summary.output_path}",
                "",
                f"Dimensiones originales (W, H, Z): {summary.original_shape}",
                f"Dimensiones exportadas (W, H, Z): {summary.final_shape}",
                f"Spacing estimado XY: {summary.spacing_xy} mm | Z: {summary.spacing_z} mm",
                f"Encoding NRRD: {summary.encoding}",
            ]
            if summary.resized_for_opus:
                lines.extend(["", "Compatibilidad OPUS aplicada automaticamente.", f"Motivo: {summary.resize_reason}"])

            messagebox.showinfo("Exito", "\n".join(lines))
            self._refresh_status(f"Exportado: {os.path.basename(summary.output_path)}")
        except Exception as e:
            self.logger.exception("Error procesando %s", self.video_actual)
            messagebox.showerror("Error", f"{e}\n\nSe guardo detalle tecnico en:\n{app_log_path()}")


def main():
    app = CubeSimulator()
    app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        get_logger().exception("Unhandled application error")
        messagebox.showerror("Error fatal", f"Ocurrio un error no controlado.\n\nRevisa el log en:\n{app_log_path()}\n\n{traceback.format_exc()}")
