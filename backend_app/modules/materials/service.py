import os
import re
import uuid
from pathlib import Path

from . import repository


def material_dir(base_dir):
    path = Path(base_dir) / "videoFile"
    path.mkdir(parents=True, exist_ok=True)
    return path


def remove_material_file(base_dir, filename):
    safe_name = sanitize_download_filename(filename)
    root = material_dir(base_dir).resolve()
    target = (root / safe_name).resolve()
    if root not in target.parents:
        raise ValueError("Invalid filename")
    if target.exists():
        target.unlink()
    return True


def sanitize_download_filename(filename):
    if not filename:
        raise ValueError("filename is required")
    if (
        ".." in filename
        or "/" in filename
        or "\\" in filename
        or Path(filename).name != filename
    ):
        raise ValueError("Invalid filename")
    return filename


def sanitize_upload_filename(filename):
    value = str(filename or "").replace("\\", "/").split("/")[-1].replace("\x00", "").strip()
    if not value or value in {".", ".."}:
        raise ValueError("Invalid upload filename")
    return value


def storage_suffix(filename):
    suffix = Path(filename).suffix.lower()
    return suffix if re.fullmatch(r"\.[a-z0-9]{1,16}", suffix) else ""


def save_temp_upload(file_storage, base_dir):
    safe_name = sanitize_upload_filename(file_storage.filename)
    generated = f"{uuid.uuid4().hex}{storage_suffix(safe_name)}"
    target = material_dir(base_dir) / generated
    file_storage.save(target)
    return generated


def save_material_upload(db_path, file_storage, base_dir, custom_filename=None):
    safe_original = sanitize_upload_filename(file_storage.filename)
    original_suffix = storage_suffix(safe_original)
    display_name = sanitize_upload_filename(custom_filename) if custom_filename else safe_original
    if custom_filename and original_suffix and not Path(display_name).suffix:
        display_name = f"{display_name}{original_suffix}"
    filename = display_name
    final_filename = f"{uuid.uuid4().hex}{original_suffix}"
    target = material_dir(base_dir) / final_filename
    file_storage.save(target)
    filesize = round(float(os.path.getsize(target)) / (1024 * 1024), 2)
    repository.add_file_record(db_path, filename, filesize, final_filename)
    return {
        "filename": filename,
        "filepath": final_filename,
    }
