import json
import logging
import os
from dataclasses import dataclass
from typing import Callable

import cv2
import numpy as np
import nrrd
import pydicom

DEFAULT_SPACING_XY = 0.1
DEFAULT_SPACING_Z = 0.1
DEFAULT_NRRD_ENCODING = "gzip"
OPUS_MAX_WIDTH = 1024
OPUS_MAX_VOXELS = 75_000_000


@dataclass
class ExportSummary:
    output_path: str
    original_shape: tuple[int, int, int]
    final_shape: tuple[int, int, int]
    spacing_xy: float
    spacing_z: float
    resized_for_opus: bool
    resize_reason: str | None
    encoding: str = DEFAULT_NRRD_ENCODING


@dataclass
class Pseudo4DClipSummary:
    output_dir: str
    clips_dir: str
    manifest_path: str
    clip_count: int
    frames_per_clip: int
    fps: float
    frame_size: tuple[int, int]
    motion_type: str
    sweep_cm: float
    fan_angle_deg: float


def app_log_path() -> str:
    appdata = os.environ.get("APPDATA") or os.getcwd()
    log_dir = os.path.join(appdata, "Cube_Simulator", "logs")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "cube_simulator.log")


def get_logger() -> logging.Logger:
    logger = logging.getLogger("cube_simulator")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(app_log_path(), encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def to_uint8_for_display(img: np.ndarray) -> np.ndarray:
    if img is None:
        return img
    if img.dtype == np.uint8:
        return img
    img_float = img.astype(np.float32)
    mn, mx = float(np.min(img_float)), float(np.max(img_float))
    if mx <= mn:
        return np.zeros_like(img_float, dtype=np.uint8)
    img_norm = (img_float - mn) / (mx - mn)
    return (img_norm * 255.0).astype(np.uint8)


def ensure_gray(frame: np.ndarray) -> np.ndarray:
    if frame is None:
        return None
    if len(frame.shape) == 2:
        return frame
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def normalize_to_uint8(frame: np.ndarray) -> np.ndarray:
    if frame is None:
        return None
    if frame.dtype == np.uint8:
        return frame
    frame_f = frame.astype(np.float32)
    mn, mx = float(np.min(frame_f)), float(np.max(frame_f))
    if mx <= mn:
        return np.zeros(frame.shape, dtype=np.uint8)
    return ((frame_f - mn) / (mx - mn) * 255.0).astype(np.uint8)


def enforce_size(frame: np.ndarray, target_h: int, target_w: int) -> np.ndarray:
    if frame is None:
        return np.zeros((target_h, target_w), dtype=np.uint8)
    h, w = frame.shape[:2]
    if h == target_h and w == target_w:
        return frame
    return cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LINEAR)


def read_middle_frame(video_path: str) -> np.ndarray | None:
    ext = os.path.splitext(video_path)[1].lower()
    frame = None

    if ext == ".dcm":
        ds = pydicom.dcmread(video_path)
        px = ds.pixel_array
        if len(px.shape) >= 3:
            mid = px.shape[0] // 2
            frame = px[mid]
        else:
            frame = px
    else:
        cap = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(total // 2, 0))
        ret, frame = cap.read()
        cap.release()
        if not ret:
            frame = None

    return frame


def read_source_fps(video_path: str) -> float:
    ext = os.path.splitext(video_path)[1].lower()
    if ext == ".dcm":
        return 12.0

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    if fps and fps > 0:
        return float(fps)
    return 12.0


def apply_anonymization(
    frame: np.ndarray,
    crop_roi: tuple[int, int, int, int] | None,
    mask_rects: list[tuple[int, int, int, int]],
    mask_mode: str,
) -> np.ndarray | None:
    if frame is None:
        return None

    out = frame.copy()

    if crop_roi is not None:
        x, y, w, h = crop_roi
        fh, fw = out.shape[:2]
        x = max(0, x)
        y = max(0, y)
        x2 = min(x + max(0, w), fw)
        y2 = min(y + max(0, h), fh)
        if x2 <= x or y2 <= y:
            return None
        out = out[y:y2, x:x2]

    if out.size == 0:
        return None

    if mask_rects:
        fh, fw = out.shape[:2]
        for (x1, y1, x2, y2) in mask_rects:
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(fw, max(0, x2))
            y2 = min(fh, max(0, y2))
            if y2 <= y1 or x2 <= x1:
                continue

            if mask_mode == "blur":
                roi = out[y1:y2, x1:x2]
                if roi.size > 0:
                    k = max(3, (min(roi.shape[0], roi.shape[1]) // 10) * 2 + 1)
                    out[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (k, k), 0)
            else:
                if len(out.shape) == 2:
                    out[y1:y2, x1:x2] = 0
                else:
                    out[y1:y2, x1:x2] = (0, 0, 0)

    if out.size == 0:
        return None
    return out


def _read_spacing_from_dicom(ds: pydicom.dataset.FileDataset) -> tuple[float, float]:
    spacing_xy = DEFAULT_SPACING_XY
    spacing_z = DEFAULT_SPACING_Z

    try:
        ps = ds.PixelSpacing
        spacing_xy = float(ps[0])
    except Exception:
        pass

    try:
        spacing_z = float(ds.SliceThickness)
    except Exception:
        pass

    return spacing_xy, spacing_z


def extract_processed_frames(
    video_path: str,
    crop_roi: tuple[int, int, int, int] | None,
    mask_rects: list[tuple[int, int, int, int]],
    mask_mode: str,
    progress_callback: Callable[[float], None] | None = None,
) -> tuple[list[np.ndarray], float, float]:
    logger = get_logger()
    ext = os.path.splitext(video_path)[1].lower()
    frames: list[np.ndarray] = []
    spacing_xy = DEFAULT_SPACING_XY
    spacing_z = DEFAULT_SPACING_Z

    if ext == ".dcm":
        ds = pydicom.dcmread(video_path)
        spacing_xy, spacing_z = _read_spacing_from_dicom(ds)
        px = ds.pixel_array
        seq = [px] if len(px.shape) == 2 else list(px)
        total = len(seq)

        for i, frame in enumerate(seq):
            anon = apply_anonymization(frame, crop_roi, mask_rects, mask_mode)
            if anon is None:
                continue
            if len(anon.shape) == 3:
                anon = ensure_gray(anon)
            anon = normalize_to_uint8(anon)
            frames.append(anon)

            if progress_callback and total > 0 and i % max(1, total // 50) == 0:
                progress_callback(i / total)
    else:
        cap = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total <= 0:
            cap.release()
            raise RuntimeError("No se pudo determinar la cantidad de frames del video.")

        for i in range(total):
            ret, frame = cap.read()
            if not ret:
                break
            anon = apply_anonymization(frame, crop_roi, mask_rects, mask_mode)
            if anon is None:
                continue
            gray = ensure_gray(anon)
            gray = normalize_to_uint8(gray)
            frames.append(gray)

            if progress_callback and i % max(1, total // 100) == 0:
                progress_callback(i / total)

        cap.release()

    if not frames:
        logger.warning("No frames were extracted for %s", video_path)
        raise RuntimeError("No se extrajeron frames validos para construir el volumen.")

    return frames, spacing_xy, spacing_z


def build_volume_from_frames(frames: list[np.ndarray]) -> np.ndarray:
    h_ref, w_ref = frames[0].shape[:2]
    frames_ok = [enforce_size(frame, h_ref, w_ref) for frame in frames]
    vol = np.stack(frames_ok, axis=0)
    return np.transpose(vol, (2, 1, 0))


def resize_volume_xy(volume: np.ndarray, target_width: int) -> np.ndarray:
    width, height, depth = volume.shape
    if width <= target_width:
        return volume

    scale = target_width / float(width)
    target_height = max(1, int(round(height * scale)))
    resized_slices = []

    for z in range(depth):
        plane_xy = volume[:, :, z].T
        resized_xy = cv2.resize(plane_xy, (target_width, target_height), interpolation=cv2.INTER_AREA)
        resized_slices.append(resized_xy.T)

    return np.stack(resized_slices, axis=2)


def enforce_opus_limits(
    volume: np.ndarray,
    max_width: int = OPUS_MAX_WIDTH,
    max_voxels: int = OPUS_MAX_VOXELS,
) -> tuple[np.ndarray, bool, str | None]:
    width, height, depth = volume.shape
    resized = volume
    reasons: list[str] = []

    if width > max_width:
        reasons.append(f"ancho {width}>{max_width}")
        resized = resize_volume_xy(resized, max_width)

    width2, height2, depth2 = resized.shape
    voxels2 = width2 * height2 * depth2
    if voxels2 > max_voxels:
        scale = (max_voxels / float(voxels2)) ** 0.5
        target_width = max(1, int(np.floor(width2 * scale)))
        if target_width < width2:
            reasons.append(f"voxels {voxels2}>{max_voxels}")
            resized = resize_volume_xy(resized, target_width)

    resized_for_opus = resized.shape != volume.shape
    reason = ", ".join(reasons) if reasons else None
    return resized, resized_for_opus, reason


def _synthetic_linear_transform(frame: np.ndarray, position: float, sweep_cm: float) -> np.ndarray:
    h, w = frame.shape[:2]
    shift_x = position * max(6.0, 0.035 * w + sweep_cm * 6.0)
    shift_y = position * max(2.0, 0.008 * h)
    matrix = np.float32([[1.0, 0.0, shift_x], [0.0, 1.0, shift_y]])
    return cv2.warpAffine(frame, matrix, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def _synthetic_fan_transform(frame: np.ndarray, position: float, fan_angle_deg: float, sweep_cm: float) -> np.ndarray:
    h, w = frame.shape[:2]
    pivot = (w / 2.0, max(10.0, 0.18 * h))
    angle = position * fan_angle_deg
    matrix = cv2.getRotationMatrix2D(pivot, angle, 1.0)
    matrix[0, 2] += position * max(4.0, 0.02 * w + sweep_cm * 4.0)
    matrix[1, 2] += abs(position) * max(1.0, 0.006 * h)
    return cv2.warpAffine(frame, matrix, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def apply_synthetic_probe_motion(
    frame: np.ndarray,
    position: float,
    motion_type: str,
    sweep_cm: float,
    fan_angle_deg: float,
) -> np.ndarray:
    if motion_type.lower().startswith("aban"):
        return _synthetic_fan_transform(frame, position, fan_angle_deg, sweep_cm)
    return _synthetic_linear_transform(frame, position, sweep_cm)


def smooth_position(z_idx: int, z_slices: int) -> float:
    if z_slices <= 1:
        return 0.0
    t = z_idx / float(z_slices - 1)
    eased = t * t * (3.0 - 2.0 * t)
    return -1.0 + 2.0 * eased


def blend_spatial_neighbors(
    frame: np.ndarray,
    position: float,
    neighbor_step: float,
    motion_type: str,
    sweep_cm: float,
    fan_angle_deg: float,
) -> np.ndarray:
    current = apply_synthetic_probe_motion(frame, position, motion_type, sweep_cm, fan_angle_deg).astype(np.float32)

    if neighbor_step <= 0:
        return current.astype(np.uint8)

    prev_position = max(-1.0, position - neighbor_step)
    next_position = min(1.0, position + neighbor_step)
    prev_frame = apply_synthetic_probe_motion(frame, prev_position, motion_type, sweep_cm, fan_angle_deg).astype(np.float32)
    next_frame = apply_synthetic_probe_motion(frame, next_position, motion_type, sweep_cm, fan_angle_deg).astype(np.float32)

    blended = cv2.addWeighted(current, 0.65, prev_frame, 0.175, 0.0)
    blended = cv2.addWeighted(blended, 0.825, next_frame, 0.175, 0.0)
    return np.clip(blended, 0, 255).astype(np.uint8)


def write_clip(path: str, frames: list[np.ndarray], fps: float) -> None:
    if not frames:
        raise RuntimeError("No hay frames para escribir el clip.")

    h, w = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    writer = cv2.VideoWriter(path, fourcc, fps, (w, h), True)
    if not writer.isOpened():
        raise RuntimeError(f"No se pudo crear el clip: {path}")

    try:
        for frame in frames:
            if len(frame.shape) == 2:
                bgr = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            else:
                bgr = frame
            writer.write(bgr)
    finally:
        writer.release()


def _sample_clip_frames(frames: list[np.ndarray], frames_per_clip: int) -> list[np.ndarray]:
    if frames_per_clip >= len(frames):
        return [frame.copy() for frame in frames]

    # Preserve the original temporal behavior by taking a contiguous window.
    start_idx = max(0, (len(frames) - frames_per_clip) // 2)
    end_idx = start_idx + frames_per_clip
    return [frame.copy() for frame in frames[start_idx:end_idx]]


def build_pseudo4d_volume(
    frames: list[np.ndarray],
    z_slices: int,
    motion_type: str,
    sweep_cm: float,
    fan_angle_deg: float,
    progress_callback: Callable[[float], None] | None = None,
) -> np.ndarray:
    if z_slices < 2:
        raise RuntimeError("Pseudo 4D necesita al menos 2 slices sinteticos en Z.")

    h_ref, w_ref = frames[0].shape[:2]
    frames_ok = [enforce_size(frame, h_ref, w_ref) for frame in frames]
    total_frames = len(frames_ok)
    pseudo_slices: list[np.ndarray] = []

    for z_idx in range(z_slices):
        frame_idx = int(round(z_idx * (total_frames - 1) / max(1, z_slices - 1))) if total_frames > 1 else 0
        position = -1.0 + (2.0 * z_idx / max(1, z_slices - 1))
        base_frame = frames_ok[frame_idx]
        transformed = apply_synthetic_probe_motion(base_frame, position, motion_type, sweep_cm, fan_angle_deg)
        pseudo_slices.append(transformed)

        if progress_callback and z_idx % max(1, z_slices // 50) == 0:
            progress_callback(z_idx / z_slices)

    vol = np.stack(pseudo_slices, axis=0)
    return np.transpose(vol, (2, 1, 0))


def export_pseudo4d_clips(
    video_path: str,
    output_dir: str,
    crop_roi: tuple[int, int, int, int] | None,
    mask_rects: list[tuple[int, int, int, int]],
    mask_mode: str,
    motion_type: str,
    sweep_cm: float,
    z_slices: int,
    fan_angle_deg: float,
    clip_duration_s: float = 2.0,
    progress_callback: Callable[[float], None] | None = None,
) -> Pseudo4DClipSummary:
    logger = get_logger()
    frames, _, _ = extract_processed_frames(
        video_path=video_path,
        crop_roi=crop_roi,
        mask_rects=mask_rects,
        mask_mode=mask_mode,
        progress_callback=None,
    )
    fps = read_source_fps(video_path)
    frames_per_clip = max(2, int(round(fps * clip_duration_s)))
    base_clip = _sample_clip_frames(frames, frames_per_clip)

    clips_dir = os.path.join(output_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    transformed_clips: list[dict[str, object]] = []
    h_ref, w_ref = base_clip[0].shape[:2]
    neighbor_step = 2.0 / max(1, z_slices - 1)

    for z_idx in range(z_slices):
        position = smooth_position(z_idx, z_slices)
        clip_frames = []
        for frame in base_clip:
            transformed = blend_spatial_neighbors(
                frame,
                position=position,
                neighbor_step=neighbor_step,
                motion_type=motion_type,
                sweep_cm=sweep_cm,
                fan_angle_deg=fan_angle_deg,
            )
            clip_frames.append(enforce_size(transformed, h_ref, w_ref))

        clip_name = f"z_{z_idx:03d}.avi"
        clip_path = os.path.join(clips_dir, clip_name)
        write_clip(clip_path, clip_frames, fps)
        transformed_clips.append({
            "index": z_idx,
            "position": round(position, 6),
            "file": clip_name,
        })

        if progress_callback and z_idx % max(1, z_slices // 50) == 0:
            progress_callback(z_idx / z_slices)

    manifest_path = os.path.join(output_dir, "manifest.json")
    manifest = {
        "mode": "pseudo4d_clips",
        "source_video": os.path.basename(video_path),
        "motion_type": motion_type,
        "sweep_cm": sweep_cm,
        "fan_angle_deg": fan_angle_deg,
        "z_slices": z_slices,
        "fps": fps,
        "clip_duration_s": clip_duration_s,
        "frames_per_clip": frames_per_clip,
        "frame_size": [w_ref, h_ref],
        "spatial_blend": "neighbor_weighted",
        "clips_dir": "clips",
        "clips": transformed_clips,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    logger.info(
        "Exported Pseudo4D clips %s clips=%s fps=%s frames_per_clip=%s motion=%s sweep_cm=%s fan_angle_deg=%s",
        output_dir,
        z_slices,
        fps,
        frames_per_clip,
        motion_type,
        sweep_cm,
        fan_angle_deg,
    )

    return Pseudo4DClipSummary(
        output_dir=output_dir,
        clips_dir=clips_dir,
        manifest_path=manifest_path,
        clip_count=z_slices,
        frames_per_clip=frames_per_clip,
        fps=fps,
        frame_size=(w_ref, h_ref),
        motion_type=motion_type,
        sweep_cm=sweep_cm,
        fan_angle_deg=fan_angle_deg,
    )


def write_nrrd(output_path: str, volume: np.ndarray, encoding: str = DEFAULT_NRRD_ENCODING) -> None:
    header = {
        "type": "uint8",
        "dimension": 3,
        "sizes": np.array(volume.shape),
        "encoding": encoding,
    }
    nrrd.write(output_path, volume.astype(np.uint8), header)


def process_to_nrrd(
    video_path: str,
    output_path: str,
    crop_roi: tuple[int, int, int, int] | None,
    mask_rects: list[tuple[int, int, int, int]],
    mask_mode: str,
    progress_callback: Callable[[float], None] | None = None,
) -> ExportSummary:
    logger = get_logger()
    frames, spacing_xy, spacing_z = extract_processed_frames(
        video_path=video_path,
        crop_roi=crop_roi,
        mask_rects=mask_rects,
        mask_mode=mask_mode,
        progress_callback=progress_callback,
    )
    volume = build_volume_from_frames(frames)
    original_shape = tuple(int(x) for x in volume.shape)
    volume, resized_for_opus, resize_reason = enforce_opus_limits(volume)
    final_shape = tuple(int(x) for x in volume.shape)

    write_nrrd(output_path, volume)
    logger.info(
        "Exported Pseudo3D NRRD %s original_shape=%s final_shape=%s resized_for_opus=%s reason=%s spacing_xy=%s spacing_z=%s",
        output_path,
        original_shape,
        final_shape,
        resized_for_opus,
        resize_reason,
        spacing_xy,
        spacing_z,
    )

    return ExportSummary(
        output_path=output_path,
        original_shape=original_shape,
        final_shape=final_shape,
        spacing_xy=spacing_xy,
        spacing_z=spacing_z,
        resized_for_opus=resized_for_opus,
        resize_reason=resize_reason,
    )
