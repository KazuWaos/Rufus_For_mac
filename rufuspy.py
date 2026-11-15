#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RufusPy para macOS  -  interfaz tipo Rufus para crear USBs de arranque.

Modos:
  * Modo imagen (DD): copia la imagen bloque a bloque a /dev/rdiskN.
        Sirve para ISOs hibridas (Ubuntu, Debian, Fedora, Tails, Raspberry Pi OS...) y .img
  * Instalacion de Windows estandar: formatea (FAT32 o exFAT, MBR o GPT), monta la ISO,
        copia los archivos y, si install.wim pesa mas de 4 GB, lo divide con wimlib.
        Opcional: autounattend.xml (sin requisitos TPM/RAM/Secure Boot, sin cuenta Microsoft...)

Requisitos:
  * Python 3 con Tkinter (python.org, o `brew install python-tk`)
  * Para ISOs de Windows con install.wim > 4 GB:  brew install wimlib
  * Pide la contrasena de administrador (dialogo nativo de macOS) al pulsar EMPEZAR.

Uso:  python3 rufuspy.py
"""
import sys, os, json, time, shutil, hashlib, plistlib, subprocess, re, select
import tempfile, threading, queue, getpass, shlex, fcntl

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    from tkinter import font as tkfont
except Exception:  # el modo --worker no necesita Tk
    tk = None

VERSION = "1.0"
GREEN, RED, GRAY = "#06b025", "#d13438", "#d0d0d0"
FAT_MAX = 4 * 1024 ** 3 - 1

# --------------------------------------------------------------------------- textos
TR = {
    "es": {
        "drive_props": "Propiedades de la unidad", "device": "Dispositivo",
        "boot_sel": "Elección de arranque", "select": "SELECCIONAR",
        "image_opt": "Opciones de imagen", "opt_dd": "Modo imagen (DD)",
        "opt_win": "Instalación de Windows estándar", "scheme": "Esquema de partición",
        "target": "Sistema destino", "tgt_bios": "BIOS o UEFI", "tgt_uefi": "UEFI (no CSM)",
        "list_hdd": "Listar discos duros USB", "fmt_opts": "Opciones de formateo",
        "label": "Etiqueta de volumen", "fs": "Sistema de archivos",
        "verify": "Verificar al terminar", "status": "Estado", "ready": "PREPARADO",
        "start": "EMPEZAR", "cancel": "CANCELAR", "close": "CERRAR", "done": "LISTO",
        "error": "ERROR", "cancelled": "CANCELADO", "detecting": "ANALIZANDO IMAGEN...",
        "found": "{n} dispositivo(s) encontrado(s)", "no_dev": "Ningún dispositivo encontrado",
        "no_iso": "(ninguna imagen)", "iso_filter": "Imágenes de disco", "all_files": "Todos los archivos",
        "choose_iso": "Selecciona una imagen de disco",
        "e_nodisk": "Selecciona un dispositivo.", "e_noiso": "Selecciona una imagen de disco.",
        "e_detect": "Todavía se está analizando la imagen. Espera un momento.",
        "e_notwin": "Esta imagen no parece una ISO de Windows. Usa el Modo imagen (DD).",
        "e_wimlib": "install.wim pesa más de 4 GB y no cabe en FAT32.\nInstala wimlib para poder dividirlo:\n\n    brew install wimlib",
        "e_toobig": "La imagen ({img}) no cabe en el dispositivo ({disk}).",
        "confirm_title": "ADVERTENCIA: SE BORRARÁN LOS DATOS",
        "confirm_body": "Se borrarán TODOS los datos de:\n\n{dev}\n\nEsta acción no se puede deshacer. ¿Continuar?",
        "confirm_exfat": "\n\nAviso: exFAT no suele arrancar en UEFI.",
        "busy_close": "Hay una operación en curso. Cancélala antes de cerrar.",
        "win_title": "Experiencia de usuario de Windows",
        "win_q": "¿Personalizar la instalación de Windows?",
        "win_hw": "Quitar requisito de 4 GB+ de RAM, Secure Boot y TPM 2.0",
        "win_ms": "Quitar requisito de cuenta Microsoft en línea",
        "win_data": "Desactivar recopilación de datos (omitir preguntas de privacidad)",
        "win_local": "Crear una cuenta local con el mismo nombre que este usuario",
        "win_region": "Usar las mismas opciones regionales que este equipo",
        "ok": "OK", "cancel_btn": "Cancelar",
        "log_title": "Registro", "about_title": "Acerca de",
        "about": "RufusPy {v} para macOS\n\nInspirado en Rufus. Modo imagen (DD) y modo Windows (FAT32 + wimlib).\n\nÚsalo bajo tu responsabilidad: escribe directamente en discos.",
        "done_msg": "Terminado. Ya puedes retirar el USB.", "auth_cancel": "Operación cancelada (no se concedieron permisos).",
        "auth_fail": "No se pudo obtener permisos de administrador:\n{e}",
        "worker_died": "El proceso de escritura terminó inesperadamente.\n{e}",
        "no_worker": "El proceso de escritura no respondió.",
        "w_start": "Iniciando...", "w_unmount": "Desmontando disco...",
        "w_write": "Escribiendo imagen... {pct:.0f}% ({speed}, quedan {eta})",
        "w_verify": "Verificando... {pct:.0f}%",
        "w_verify_bad": "La verificación falló: lo escrito no coincide con la imagen.",
        "w_mount": "Montando la ISO...", "w_format": "Formateando el USB...",
        "w_copy": "Copiando archivos... {pct:.0f}% ({speed})",
        "w_split": "Dividiendo install.wim (FAT32)... {pct:.0f}%",
        "w_unattend": "Creando autounattend.xml...", "w_finish": "Finalizando y expulsando...",
        "w_bad_disk": "{disk} no es un disco externo válido (o cambió de tamaño).",
        "w_toobig": "La imagen ({img}) no cabe en el disco ({disk}).",
        "w_big_file": "El archivo {f} supera 4 GB y no cabe en FAT32.",
        "w_cmd_fail": "Falló el comando: {cmd}\n{out}", "w_size_mismatch": "Tamaño incorrecto al copiar {f}.",
        "w_no_mount": "No se pudo montar la ISO.", "w_no_vol": "No se encontró el volumen del USB tras formatear.",
        "w_unexpected": "Error inesperado: {e}", "w_cancelled": "Cancelado por el usuario. El USB puede haber quedado a medias.",
    },
    "en": {
        "drive_props": "Drive Properties", "device": "Device", "boot_sel": "Boot selection",
        "select": "SELECT", "image_opt": "Image option", "opt_dd": "DD image mode",
        "opt_win": "Standard Windows installation", "scheme": "Partition scheme",
        "target": "Target system", "tgt_bios": "BIOS or UEFI", "tgt_uefi": "UEFI (non CSM)",
        "list_hdd": "List USB Hard Drives", "fmt_opts": "Format Options", "label": "Volume label",
        "fs": "File system", "verify": "Verify when finished", "status": "Status", "ready": "READY",
        "start": "START", "cancel": "CANCEL", "close": "CLOSE", "done": "DONE", "error": "ERROR",
        "cancelled": "CANCELLED", "detecting": "ANALYZING IMAGE...",
        "found": "{n} device(s) found", "no_dev": "No device found", "no_iso": "(no image)",
        "iso_filter": "Disk images", "all_files": "All files", "choose_iso": "Select a disk image",
        "e_nodisk": "Select a device.", "e_noiso": "Select a disk image.",
        "e_detect": "The image is still being analyzed. Please wait a moment.",
        "e_notwin": "This image does not look like a Windows ISO. Use DD image mode.",
        "e_wimlib": "install.wim is larger than 4 GB and won't fit on FAT32.\nInstall wimlib to split it:\n\n    brew install wimlib",
        "e_toobig": "The image ({img}) does not fit on the device ({disk}).",
        "confirm_title": "WARNING: ALL DATA WILL BE DESTROYED",
        "confirm_body": "ALL data on:\n\n{dev}\n\nwill be destroyed. This cannot be undone. Continue?",
        "confirm_exfat": "\n\nNote: exFAT usually does not boot on UEFI.",
        "busy_close": "An operation is in progress. Cancel it before closing.",
        "win_title": "Windows User Experience", "win_q": "Customize Windows installation?",
        "win_hw": "Remove requirement for 4GB+ RAM, Secure Boot and TPM 2.0",
        "win_ms": "Remove requirement for an online Microsoft account",
        "win_data": "Disable data collection (Skip privacy questions)",
        "win_local": "Set a local account using the same name as this user's",
        "win_region": "Set regional options using the same values as this user's",
        "ok": "OK", "cancel_btn": "Cancel", "log_title": "Log", "about_title": "About",
        "about": "RufusPy {v} for macOS\n\nInspired by Rufus. DD image mode and Windows mode (FAT32 + wimlib).\n\nUse at your own risk: it writes directly to disks.",
        "done_msg": "Finished. You can now remove the USB drive.", "auth_cancel": "Operation cancelled (permission not granted).",
        "auth_fail": "Could not obtain administrator privileges:\n{e}",
        "worker_died": "The writer process ended unexpectedly.\n{e}",
        "no_worker": "The writer process did not respond.",
        "w_start": "Starting...", "w_unmount": "Unmounting disk...",
        "w_write": "Writing image... {pct:.0f}% ({speed}, {eta} left)", "w_verify": "Verifying... {pct:.0f}%",
        "w_verify_bad": "Verification failed: written data does not match the image.",
        "w_mount": "Mounting ISO...", "w_format": "Formatting USB drive...",
        "w_copy": "Copying files... {pct:.0f}% ({speed})", "w_split": "Splitting install.wim (FAT32)... {pct:.0f}%",
        "w_unattend": "Creating autounattend.xml...", "w_finish": "Finishing and ejecting...",
        "w_bad_disk": "{disk} is not a valid external disk (or its size changed).",
        "w_toobig": "The image ({img}) does not fit on the disk ({disk}).",
        "w_big_file": "File {f} is larger than 4 GB and won't fit on FAT32.",
        "w_cmd_fail": "Command failed: {cmd}\n{out}", "w_size_mismatch": "Wrong size after copying {f}.",
        "w_no_mount": "Could not mount the ISO.", "w_no_vol": "USB volume not found after formatting.",
        "w_unexpected": "Unexpected error: {e}", "w_cancelled": "Cancelled by user. The USB drive may be left half-written.",
    },
}


def T(lang, key, **kw):
    s = TR.get(lang, TR["en"]).get(key) or TR["en"].get(key) or key
    return s.format(**kw) if kw else s


# --------------------------------------------------------------------------- utilidades
class Fail(Exception):
    pass


class Cancelled(Exception):
    pass


def hsize(n):
    n = float(n)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1000 or u == "TB":
            s = f"{n:.0f}" if (u == "B" or n >= 100) else f"{n:.1f}"
            return f"{s} {u}"
        n /= 1000


def fmt_time(s):
    s = int(max(0, s))
    h, r = divmod(s, 3600)
    m, sec = divmod(r, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def sh_plist(cmd):
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode(errors="replace"))
    return plistlib.loads(r.stdout)


def list_disks(include_hdd=False):
    """Discos externos fisicos (nunca los internos)."""
    res = []
    data = sh_plist(["diskutil", "list", "-plist", "external", "physical"])
    for d in data.get("AllDisksAndPartitions", []):
        ident = d.get("DeviceIdentifier")
        if not ident:
            continue
        try:
            info = sh_plist(["diskutil", "info", "-plist", ident])
        except Exception:
            continue
        if info.get("Internal", False) or not info.get("WholeDisk", True):
            continue
        if info.get("VirtualOrPhysical") == "Virtual":
            continue
        removable = bool(info.get("RemovableMedia") or info.get("Removable"))
        if not removable and not include_hdd:
            continue
        size = info.get("TotalSize") or info.get("Size") or d.get("Size") or 0
        name = ""
        for p in d.get("Partitions", []):
            if p.get("VolumeName"):
                name = p["VolumeName"]
                break
        name = name or info.get("MediaName") or info.get("IORegistryEntryName") or "USB"
        res.append({"id": ident, "name": name, "size": size})
    return res


def attach_iso(path):
    r = subprocess.run(["hdiutil", "attach", "-nobrowse", "-readonly", "-noverify", "-plist", path],
                       capture_output=True)
    if r.returncode != 0:
        raise Fail(r.stderr.decode(errors="replace"))
    for e in plistlib.loads(r.stdout).get("system-entities", []):
        if e.get("mount-point"):
            return e["mount-point"]
    raise Fail("no mount point")


def detach_iso(mp):
    subprocess.run(["hdiutil", "detach", mp, "-force"], capture_output=True)


def detect_iso(path):
    """Devuelve {'windows': bool, 'wim_size': int}."""
    info = {"windows": False, "wim_size": 0}
    try:
        mp = attach_iso(path)
    except Exception:
        return info
    try:
        s = os.path.join(mp, "sources")
        if os.path.isdir(s):
            names = {n.lower(): n for n in os.listdir(s)}
            if {"install.wim", "install.esd", "boot.wim"} & set(names):
                info["windows"] = True
            for k in ("install.wim", "install.esd"):
                if k in names:
                    info["wim_size"] = os.path.getsize(os.path.join(s, names[k]))
                    break
    except Exception:
        pass
    finally:
        detach_iso(mp)
    return info


def find_wimlib():
    for c in ("wimlib-imagex", "/opt/homebrew/bin/wimlib-imagex", "/usr/local/bin/wimlib-imagex"):
        p = shutil.which(c) or (c if os.path.isfile(c) else None)
        if p:
            return p
    return None


def mac_locale_tag():
    try:
        out = subprocess.run(["defaults", "read", "-g", "AppleLocale"], capture_output=True, text=True).stdout.strip()
        m = re.match(r"([a-z]{2,3})_([A-Z]{2})", out)
        if m:
            return f"{m.group(1)}-{m.group(2)}"
    except Exception:
        pass
    return "en-US"


def mac_lang():
    try:
        out = subprocess.run(["defaults", "read", "-g", "AppleLanguages"], capture_output=True, text=True).stdout
        m = re.search(r'"?([a-z]{2})', out.split("(", 1)[-1])
        if m and m.group(1) != "es":
            return "en"
    except Exception:
        pass
    return "es"


def build_unattend(o, user, tag):
    """autounattend.xml segun las casillas elegidas."""
    from xml.sax.saxutils import escape
    ns = ('processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" '
          'versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State" '
          'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"')

    def runsync(cmds):
        x = "<RunSynchronous>\n"
        for i, c in enumerate(cmds, 1):
            x += (f'<RunSynchronousCommand wcm:action="add"><Order>{i}</Order>'
                  f"<Path>{escape(c)}</Path></RunSynchronousCommand>\n")
        return x + "</RunSynchronous>\n"

    passes = ""
    if o.get("hw"):
        cmds = [f"reg add HKLM\\SYSTEM\\Setup\\LabConfig /v {k} /t REG_DWORD /d 1 /f"
                for k in ("BypassTPMCheck", "BypassSecureBootCheck", "BypassRAMCheck")]
        passes += (f'<settings pass="windowsPE"><component name="Microsoft-Windows-Setup" {ns}>\n'
                   f"{runsync(cmds)}</component></settings>\n")
    if o.get("ms"):
        cmd = r"reg add HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\OOBE /v BypassNRO /t REG_DWORD /d 1 /f"
        passes += (f'<settings pass="specialize"><component name="Microsoft-Windows-Deployment" {ns}>\n'
                   f"{runsync([cmd])}</component></settings>\n")
    oobe = ""
    if o.get("data"):
        oobe += "<HideEULAPage>true</HideEULAPage><ProtectYourPC>3</ProtectYourPC>"
    if o.get("ms") or o.get("local"):
        oobe += "<HideOnlineAccountScreens>true</HideOnlineAccountScreens>"
    if o.get("local"):
        oobe += "<HideLocalAccountScreen>true</HideLocalAccountScreen>"
    comp = ""
    if oobe:
        comp += f"<OOBE>{oobe}</OOBE>\n"
    if o.get("local"):
        u = escape(user)
        comp += (f'<UserAccounts><LocalAccounts><LocalAccount wcm:action="add"><Name>{u}</Name>'
                 f"<DisplayName>{u}</DisplayName><Group>Administrators</Group>"
                 f"<Password><Value></Value><PlainText>true</PlainText></Password>"
                 f"</LocalAccount></LocalAccounts></UserAccounts>\n")
    oobe_pass = ""
    if comp:
        oobe_pass += f'<component name="Microsoft-Windows-Shell-Setup" {ns}>\n{comp}</component>\n'
    if o.get("region"):
        oobe_pass += (f'<component name="Microsoft-Windows-International-Core" {ns}>'
                      f"<InputLocale>{tag}</InputLocale><SystemLocale>{tag}</SystemLocale>"
                      f"<UserLocale>{tag}</UserLocale></component>\n")
    if oobe_pass:
        passes += f'<settings pass="oobeSystem">\n{oobe_pass}</settings>\n'
    if not passes:
        return ""
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<unattend xmlns="urn:schemas-microsoft-com:unattend">\n' + passes + "</unattend>\n")


# --------------------------------------------------------------------------- worker (root)
class Prog:
    def __init__(self, jd, lang):
        self.jd, self.lang = jd, lang
        self.pf = os.path.join(jd, "progress.json")
        self.lf = os.path.join(jd, "log.txt")
        self.cf = os.path.join(jd, "cancel")
        self.last = 0

    def set(self, state, pct, text, force=False):
        now = time.time()
        if not force and state == "running" and now - self.last < 0.2:
            return
        self.last = now
        tmp = self.pf + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"state": state, "pct": pct, "text": text, "pid": os.getpid()}, f)
        os.chmod(tmp, 0o644)
        os.replace(tmp, self.pf)

    def log(self, msg):
        with open(self.lf, "a") as f:
            f.write(msg + "\n")
        try:
            os.chmod(self.lf, 0o644)
        except OSError:
            pass

    def t(self, key, **kw):
        return T(self.lang, key, **kw)

    def check(self):
        if os.path.exists(self.cf):
            raise Cancelled()


def run_ok(cmd, P):
    r = subprocess.run(cmd, capture_output=True, text=True)
    P.log("$ " + " ".join(cmd))
    if r.returncode != 0:
        raise Fail(P.t("w_cmd_fail", cmd=" ".join(cmd), out=(r.stdout + r.stderr).strip()))
    return r.stdout


def validate_disk(job, P):
    disk = job["disk"]
    if not re.fullmatch(r"disk\d+", disk):
        raise Fail(P.t("w_bad_disk", disk=disk))
    info = sh_plist(["diskutil", "info", "-plist", "/dev/" + disk])
    size = info.get("TotalSize") or info.get("Size")
    if (info.get("Internal") or not info.get("WholeDisk", True)
            or info.get("VirtualOrPhysical") == "Virtual" or (size and size != job["size"])):
        raise Fail(P.t("w_bad_disk", disk=disk))


def read_exact(fd, n):
    buf = b""
    while len(buf) < n:
        chunk = os.read(fd, n - len(buf))
        if not chunk:
            break
        buf += chunk
    return buf


def full_sync(fd):
    try:
        fcntl.fcntl(fd, getattr(fcntl, "F_FULLFSYNC", 51))
    except OSError:
        os.fsync(fd)


def do_dd(job, P):
    disk, img = job["disk"], job["image"]
    size = os.path.getsize(img)
    if size > job["size"]:
        raise Fail(P.t("w_toobig", img=hsize(size), disk=hsize(job["size"])))
    P.set("running", 0, P.t("w_unmount"), True)
    run_ok(["diskutil", "unmountDisk", "force", "/dev/" + disk], P)
    BS = 4 << 20
    verify = job.get("verify")
    span = 50.0 if verify else 100.0
    h = hashlib.sha256()
    done, t0 = 0, time.time()
    fd = os.open("/dev/r" + disk, os.O_WRONLY)
    try:
        with open(img, "rb") as src:
            while True:
                P.check()
                buf = src.read(BS)
                if not buf:
                    break
                h.update(buf)
                if len(buf) % 512:
                    buf += b"\0" * (512 - len(buf) % 512)
                mv, off = memoryview(buf), 0
                while off < len(mv):
                    off += os.write(fd, mv[off:])
                done += len(buf)
                el = max(time.time() - t0, 0.001)
                speed = done / el
                eta = (size - min(done, size)) / speed if speed else 0
                P.set("running", min(done, size) / size * span,
                      P.t("w_write", pct=min(done, size) / size * 100, speed=hsize(speed) + "/s", eta=fmt_time(eta)))
        full_sync(fd)
    finally:
        os.close(fd)
    if verify:
        padded = size + (-size % 512)
        h2, got, remaining = hashlib.sha256(), 0, padded
        fd = os.open("/dev/r" + disk, os.O_RDONLY)
        try:
            while remaining > 0:
                P.check()
                n = min(BS, remaining)
                data = read_exact(fd, n)
                take = min(len(data), size - got)
                if take > 0:
                    h2.update(data[:take])
                    got += take
                remaining -= n
                P.set("running", 50 + (padded - remaining) / padded * 50,
                      P.t("w_verify", pct=(padded - remaining) / padded * 100))
        finally:
            os.close(fd)
        if h.digest() != h2.digest():
            raise Fail(P.t("w_verify_bad"))
    P.set("running", 100, P.t("w_finish"), True)
    subprocess.run(["diskutil", "eject", "/dev/" + disk], capture_output=True)


def find_mount(disk, P):
    for _ in range(10):
        d = sh_plist(["diskutil", "list", "-plist", "/dev/" + disk])
        for dd in d.get("AllDisksAndPartitions", []):
            for part in dd.get("Partitions", []):
                if part.get("MountPoint"):
                    return part["MountPoint"]
        time.sleep(0.5)
    raise Fail(P.t("w_no_vol"))


def do_windows(job, P):
    disk, fs = job["disk"], job["fs"]
    P.set("running", 0, P.t("w_mount"), True)
    try:
        mp = attach_iso(job["image"])
    except Fail:
        raise Fail(P.t("w_no_mount"))
    detached = False
    try:
        files, total = [], 0
        for root, _dirs, names in os.walk(mp):
            for fn in names:
                p = os.path.join(root, fn)
                if os.path.islink(p):
                    continue
                sz = os.path.getsize(p)
                files.append((p, os.path.relpath(p, mp), sz))
                total += sz
        split = []
        if fs == "FAT32":
            for p, rel, sz in files:
                if sz > FAT_MAX:
                    if rel.lower() == os.path.join("sources", "install.wim") and job.get("wimlib"):
                        split.append((p, rel, sz))
                    else:
                        raise Fail(P.t("w_big_file", f=rel))
        split_set = {r for _, r, _ in split}
        total = max(total, 1)

        label = job["label"].upper() if fs == "FAT32" else job["label"]
        label = re.sub(r"[^A-Za-z0-9 _-]", "_", label)[:11].strip() or "USB"
        P.set("running", 0, P.t("w_format"), True)
        run_ok(["diskutil", "eraseDisk", "FAT32" if fs == "FAT32" else "ExFAT", label,
                "MBR" if job["scheme"] == "MBR" else "GPT", "/dev/" + disk], P)
        dest = find_mount(disk, P)
        P.log("dest: " + dest)

        copied, t0 = 0, time.time()
        for p, rel, sz in files:
            if rel in split_set:
                continue
            dst = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(p, "rb") as a, open(dst, "wb") as b:
                while True:
                    P.check()
                    buf = a.read(1 << 20)
                    if not buf:
                        break
                    b.write(buf)
                    copied += len(buf)
                    speed = copied / max(time.time() - t0, 0.001)
                    P.set("running", copied / total * 100,
                          P.t("w_copy", pct=copied / total * 100, speed=hsize(speed) + "/s"))
            if os.path.getsize(dst) != sz:
                raise Fail(P.t("w_size_mismatch", f=rel))

        for p, rel, sz in split:
            outdir = os.path.join(dest, "sources")
            os.makedirs(outdir, exist_ok=True)
            cmd = [job["wimlib"], "split", p, os.path.join(outdir, "install.swm"), "3800"]
            P.log("$ " + " ".join(cmd))
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            buf = b""
            base = copied
            try:
                while True:
                    r, _, _ = select.select([proc.stdout], [], [], 0.5)
                    if r:
                        chunk = os.read(proc.stdout.fileno(), 4096)
                        if not chunk:
                            break
                        buf = (buf + chunk)[-400:]
                        m = re.findall(rb"(\d+)%", buf)
                        if m:
                            frac = min(int(m[-1]), 100) / 100.0
                            P.set("running", (base + sz * frac) / total * 100, P.t("w_split", pct=frac * 100))
                    P.check()
                    if proc.poll() is not None and not r:
                        break
            finally:
                if proc.poll() is None:
                    proc.terminate()
            if proc.wait() != 0:
                raise Fail(P.t("w_cmd_fail", cmd=" ".join(cmd), out=buf.decode(errors="replace")))
            copied += sz

        if job.get("unattend"):
            P.set("running", 99, P.t("w_unattend"), True)
            with open(os.path.join(dest, "autounattend.xml"), "w", encoding="utf-8") as f:
                f.write(job["unattend"])

        P.set("running", 100, P.t("w_finish"), True)
        os.sync()
        detach_iso(mp)
        detached = True
        subprocess.run(["diskutil", "eject", "/dev/" + disk], capture_output=True)
    finally:
        if not detached:
            detach_iso(mp)


def worker_main(jobfile):
    jd = os.path.dirname(jobfile)
    with open(jobfile) as f:
        job = json.load(f)
    P = Prog(jd, job.get("lang", "es"))
    try:
        P.set("running", 0, P.t("w_start"), True)
        validate_disk(job, P)
        if job["mode"] == "dd":
            do_dd(job, P)
        else:
            do_windows(job, P)
        P.set("done", 100, P.t("done"), True)
    except Cancelled:
        P.log(P.t("w_cancelled"))
        P.set("cancelled", 100, P.t("w_cancelled"), True)
    except Fail as e:
        P.log(str(e))
        P.set("error", 100, str(e), True)
    except Exception as e:  # noqa
        import traceback
        P.log(traceback.format_exc())
        P.set("error", 100, P.t("w_unexpected", e=e), True)


# --------------------------------------------------------------------------- interfaz
if tk is not None:
    class Bar(tk.Canvas):
        def __init__(self, master):
            super().__init__(master, height=20, highlightthickness=1, highlightbackground="#a0a0a0", bg=GRAY)
            self.pct, self.text, self.color = 100, "", GREEN
            self.bind("<Configure>", lambda e: self.redraw())

        def set(self, pct, text, color=GREEN):
            self.pct, self.text, self.color = pct, text, color
            self.redraw()

        def redraw(self):
            self.delete("all")
            w, h = self.winfo_width(), self.winfo_height()
            self.create_rectangle(0, 0, w * self.pct / 100.0, h, fill=self.color, width=0)
            self.create_text(w / 2, h / 2, text=self.text, fill="#ffffff" if (self.pct >= 50 and self.color != GRAY) else "#000000")


    class App:
        def __init__(self):
            self.root = tk.Tk()
            self.root.title(f"RufusPy {VERSION}")
            self.root.resizable(False, False)
            self.lang = mac_lang()
            self.q = queue.Queue()
            self.tw = []            # (widget, key) traducibles
            self.disks, self.iso_path, self.iso_info = [], "", None
            self.busy = self.refreshing = False
            self.job = None
            self.log_lines, self.logwin, self.logtext = [], None, None
            self.bar_key = "ready"
            self.t_start = 0

            base = tkfont.nametofont("TkDefaultFont")
            fam = base.actual("family")
            for nm in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkFixedFont"):
                try:
                    tkfont.nametofont(nm).configure(size=9)
                except tk.TclError:
                    pass
            self.h1 = tkfont.Font(family=fam, size=14)

            f = ttk.Frame(self.root, padding=(10, 4, 10, 2))
            f.grid(sticky="nsew")
            f.columnconfigure(0, weight=1, uniform="c")
            f.columnconfigure(1, weight=1, uniform="c")
            self.f = f
            r = 0

            def section(key):
                nonlocal r
                row = ttk.Frame(f)
                row.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(4, 1))
                row.columnconfigure(1, weight=1)
                lb = ttk.Label(row, font=self.h1)
                lb.grid(row=0, column=0)
                ttk.Separator(row).grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))
                self.reg(lb, key)
                r += 1

            def label(key, col=0, span=1):
                nonlocal r
                lb = ttk.Label(f)
                lb.grid(row=r, column=col, columnspan=span, sticky="w", pady=(2, 0))
                self.reg(lb, key)

            # --- unidad
            section("drive_props")
            label("device", 0, 2); r += 1
            self.disk_cb = ttk.Combobox(f, state="readonly", width=30)
            self.disk_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_ready())
            self.disk_cb.grid(row=r, column=0, columnspan=2, sticky="ew"); r += 1
            label("boot_sel", 0, 2); r += 1
            fr = ttk.Frame(f); fr.grid(row=r, column=0, columnspan=2, sticky="ew"); fr.columnconfigure(0, weight=1)
            self.iso_var = tk.StringVar()
            self.iso_entry = ttk.Entry(fr, textvariable=self.iso_var, state="readonly", width=16)
            self.iso_entry.grid(row=0, column=0, sticky="ew")
            self.check_lbl = ttk.Label(fr, text="", foreground="#1a7fd4")
            self.check_lbl.grid(row=0, column=1, padx=8)
            self.sel_btn = ttk.Button(fr, command=self.choose_iso)
            self.sel_btn.grid(row=0, column=2)
            self.reg(self.sel_btn, "select"); r += 1
            label("image_opt", 0, 2); r += 1
            self.mode_cb = ttk.Combobox(f, state="readonly", width=16)
            self.mode_cb.grid(row=r, column=0, columnspan=2, sticky="ew")
            self.mode_cb.bind("<<ComboboxSelected>>", lambda e: self.on_mode()); r += 1
            label("scheme", 0); label("target", 1); r += 1
            self.scheme_cb = ttk.Combobox(f, state="readonly", values=["MBR", "GPT"], width=10)
            self.scheme_cb.grid(row=r, column=0, sticky="ew", padx=(0, 4))
            self.target_cb = ttk.Combobox(f, state="readonly", width=10)
            self.target_cb.grid(row=r, column=1, sticky="ew", padx=(4, 0))
            self.scheme_cb.bind("<<ComboboxSelected>>", lambda e: self.target_cb.current(0 if self.scheme_cb.current() == 0 else 1))
            self.target_cb.bind("<<ComboboxSelected>>", lambda e: self.scheme_cb.current(0 if self.target_cb.current() == 0 else 1)); r += 1
            self.hdd_var = tk.BooleanVar(value=False)
            self.hdd_chk = ttk.Checkbutton(f, variable=self.hdd_var, command=self.refresh)
            self.hdd_chk.grid(row=r, column=0, columnspan=2, sticky="w", pady=(2, 0))
            self.reg(self.hdd_chk, "list_hdd"); r += 1

            # --- formato
            section("fmt_opts")
            label("label", 0, 2); r += 1
            self.label_var = tk.StringVar()
            self.label_entry = ttk.Entry(f, textvariable=self.label_var)
            self.label_entry.grid(row=r, column=0, columnspan=2, sticky="ew"); r += 1
            label("fs", 0); r += 1
            self.fs_cb = ttk.Combobox(f, state="readonly", values=["FAT32", "exFAT"], width=10)
            self.fs_cb.grid(row=r, column=0, sticky="ew", padx=(0, 4))
            self.verify_var = tk.BooleanVar(value=True)
            self.verify_chk = ttk.Checkbutton(f, variable=self.verify_var)
            self.verify_chk.grid(row=r, column=1, sticky="w", padx=(4, 0))
            self.reg(self.verify_chk, "verify"); r += 1

            # --- estado
            section("status")
            self.bar = Bar(f)
            self.bar.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(1, 3)); r += 1

            bt = ttk.Frame(f); bt.grid(row=r, column=0, columnspan=2, sticky="ew"); r += 1
            bt.columnconfigure(3, weight=1)
            self.lang_btn = ttk.Button(bt, width=3, command=self.toggle_lang)
            self.lang_btn.grid(row=0, column=0, padx=(0, 4))
            ttk.Button(bt, text="\u24d8", width=3, command=self.about).grid(row=0, column=1, padx=4)
            ttk.Button(bt, text="\u2630", width=3, command=self.show_log).grid(row=0, column=2, padx=4)
            self.start_btn = ttk.Button(bt, command=self.on_start_cancel, width=8)
            self.start_btn.grid(row=0, column=4, padx=3)
            self.close_btn = ttk.Button(bt, command=self.on_close, width=8)
            self.close_btn.grid(row=0, column=5)
            self.reg(self.close_btn, "close")

            sb = ttk.Frame(f); sb.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(3, 0))
            sb.columnconfigure(0, weight=1)
            self.left = ttk.Label(sb); self.left.grid(row=0, column=0, sticky="w")
            self.timer = ttk.Label(sb, text="00:00:00"); self.timer.grid(row=0, column=1, sticky="e")

            self.apply_lang()
            self.scheme_cb.current(1)
            self.target_cb.current(1)
            self.fs_cb.current(0)
            self.mode_cb.current(0)
            self.on_mode()
            self.root.protocol("WM_DELETE_WINDOW", self.on_close)
            self.root.after(100, self._pump)
            self.root.after(200, self._auto_refresh)
            self.root.after(500, self._tick)

        # ---- traduccion
        def reg(self, w, key):
            self.tw.append((w, key))

        def t(self, key, **kw):
            return T(self.lang, key, **kw)

        def apply_lang(self):
            for w, k in self.tw:
                w.configure(text=self.t(k))
            ms = self.mode_cb.current()
            self.mode_cb["values"] = [self.t("opt_dd"), self.t("opt_win")]
            self.mode_cb.current(ms if ms >= 0 else 0)
            ts = self.target_cb.current()
            self.target_cb["values"] = [self.t("tgt_bios"), self.t("tgt_uefi")]
            self.target_cb.current(ts if ts >= 0 else 1)
            self.lang_btn.configure(text="EN" if self.lang == "es" else "ES")
            self.start_btn.configure(text=self.t("cancel" if self.busy else "start"))
            if not self.iso_path:
                self.iso_var.set(self.t("no_iso"))
            self.set_bar_key(self.bar_key)
            self.update_left()

        def toggle_lang(self):
            if self.busy:
                return
            self.lang = "en" if self.lang == "es" else "es"
            self.apply_lang()

        def set_bar_key(self, key):
            self.bar_key = key
            if key in ("error", "cancelled"):
                col = RED
            elif key == "done":
                col = GREEN
            else:
                col = GRAY
            self.bar.set(100, self.t(key), col)

        def is_ready(self):
            return self.cur_disk() is not None and self.iso_info is not None

        def refresh_ready(self):
            if not self.busy and self.bar_key == "ready":
                self.set_bar_key("ready")

        def update_left(self):
            n = len(self.disks)
            self.left.configure(text=self.t("found", n=n) if n else self.t("no_dev"))

        # ---- cola de eventos hilo -> GUI
        def bg(self, target, *a):
            threading.Thread(target=target, args=a, daemon=True).start()

        def _pump(self):
            try:
                while True:
                    fn, args = self.q.get_nowait()
                    fn(*args)
            except queue.Empty:
                pass
            self.root.after(100, self._pump)

        def _tick(self):
            if self.busy:
                s = int(time.time() - self.t_start)
                self.timer.configure(text=f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}")
            self.root.after(500, self._tick)

        # ---- dispositivos
        def _auto_refresh(self):
            self.refresh()
            self.root.after(4000, self._auto_refresh)

        def refresh(self):
            if self.busy or self.refreshing:
                return
            self.refreshing = True
            self.bg(self._refresh_thread, self.hdd_var.get())

        def _refresh_thread(self, inc):
            try:
                d = list_disks(inc)
            except Exception:
                d = []
            self.q.put((self._set_disks, (d,)))

        def cur_disk(self):
            i = self.disk_cb.current()
            return self.disks[i] if 0 <= i < len(self.disks) else None

        def _set_disks(self, d):
            self.refreshing = False
            if self.busy:
                return
            sel = self.cur_disk()
            if [x["id"] for x in d] == [x["id"] for x in self.disks]:
                self.disks = d
                self.update_left()
                self.refresh_ready()
                return
            self.disks = d
            self.disk_cb["values"] = [f"{x['name']} ({x['id']}) [{hsize(x['size'])}]" for x in d]
            idx = next((i for i, x in enumerate(d) if sel and x["id"] == sel["id"]), 0 if d else -1)
            if idx >= 0:
                self.disk_cb.current(idx)
            else:
                self.disk_cb.set("")
            self.update_left()
            self.refresh_ready()

        # ---- imagen
        def choose_iso(self):
            p = filedialog.askopenfilename(
                title=self.t("choose_iso"),
                filetypes=[(self.t("iso_filter"), "*.iso *.img *.raw"), (self.t("all_files"), "*")])
            if not p:
                return
            self.iso_path, self.iso_info = p, None
            self.iso_var.set(os.path.basename(p))
            self.check_lbl.configure(text="")
            self.label_var.set(os.path.splitext(os.path.basename(p))[0][:32])
            self.set_bar_key("detecting")
            self.bg(self._detect_thread, p)

        def _detect_thread(self, p):
            self.q.put((self._detected, (p, detect_iso(p))))

        def _detected(self, p, info):
            if p != self.iso_path:
                return
            self.iso_info = info
            self.check_lbl.configure(text="\u2713")
            self.mode_cb.current(1 if info["windows"] else 0)
            self.on_mode()
            if not self.busy:
                self.set_bar_key("ready")

        def on_mode(self):
            win = self.mode_cb.current() == 1
            st = "readonly" if win else "disabled"
            self.scheme_cb.configure(state=st)
            self.target_cb.configure(state=st)
            self.fs_cb.configure(state=st)
            self.label_entry.configure(state="normal" if win else "disabled")
            self.verify_chk.configure(state="disabled" if win else "normal")

        def set_busy(self, b):
            self.busy = b
            self.start_btn.configure(text=self.t("cancel" if b else "start"))
            for w in (self.disk_cb, self.mode_cb):
                w.configure(state="disabled" if b else "readonly")
            for w in (self.sel_btn, self.hdd_chk, self.lang_btn):
                w.configure(state="disabled" if b else "normal")
            if b:
                for w in (self.scheme_cb, self.target_cb, self.fs_cb, self.label_entry, self.verify_chk):
                    w.configure(state="disabled")
            else:
                self.on_mode()

        # ---- registro
        def log(self, msg):
            self.log_lines.append(msg)
            if self.logtext is not None:
                try:
                    self.logtext.insert("end", msg + "\n")
                    self.logtext.see("end")
                except tk.TclError:
                    self.logtext = None

        def show_log(self):
            if self.logwin is not None:
                try:
                    self.logwin.lift()
                    return
                except tk.TclError:
                    pass
            w = tk.Toplevel(self.root)
            w.title(self.t("log_title"))
            t = tk.Text(w, width=90, height=24)
            sc = ttk.Scrollbar(w, command=t.yview)
            t.configure(yscrollcommand=sc.set)
            t.pack(side="left", fill="both", expand=True)
            sc.pack(side="right", fill="y")
            t.insert("end", "\n".join(self.log_lines) + ("\n" if self.log_lines else ""))
            self.logwin, self.logtext = w, t
            w.protocol("WM_DELETE_WINDOW", lambda: (setattr(self, "logtext", None), setattr(self, "logwin", None), w.destroy()))

        def about(self):
            messagebox.showinfo(self.t("about_title"), self.t("about", v=VERSION))

        # ---- dialogo de personalizacion de Windows
        def win_dialog(self):
            d = tk.Toplevel(self.root)
            d.title(self.t("win_title"))
            d.transient(self.root)
            d.resizable(False, False)
            fr = ttk.Frame(d, padding=16)
            fr.grid()
            ttk.Label(fr, text=self.t("win_q")).grid(sticky="w", pady=(0, 8))
            vars_ = {}
            for k, default in (("hw", True), ("ms", True), ("data", True), ("local", False), ("region", False)):
                vars_[k] = tk.BooleanVar(value=default)
                ttk.Checkbutton(fr, text=self.t("win_" + k), variable=vars_[k]).grid(sticky="w", pady=2)
            res = {"v": None}

            def ok():
                res["v"] = {k: v.get() for k, v in vars_.items()}
                d.destroy()

            bt = ttk.Frame(fr); bt.grid(sticky="e", pady=(12, 0))
            ttk.Button(bt, text=self.t("ok"), command=ok).grid(row=0, column=0, padx=6)
            ttk.Button(bt, text=self.t("cancel_btn"), command=d.destroy).grid(row=0, column=1)
            d.update_idletasks()
            d.grab_set()
            self.root.wait_window(d)
            return res["v"]

        # ---- inicio / cancelar
        def on_start_cancel(self):
            if self.busy:
                if self.job:
                    open(os.path.join(self.job["dir"], "cancel"), "w").close()
                return
            disk = self.cur_disk()
            if not disk:
                return messagebox.showerror(self.t("start"), self.t("e_nodisk"))
            if not self.iso_path or not os.path.isfile(self.iso_path):
                return messagebox.showerror(self.t("start"), self.t("e_noiso"))
            if self.iso_info is None:
                return messagebox.showinfo(self.t("start"), self.t("e_detect"))
            win = self.mode_cb.current() == 1
            fs = self.fs_cb.get()
            wimlib = find_wimlib()
            if win:
                if not self.iso_info["windows"]:
                    return messagebox.showerror(self.t("start"), self.t("e_notwin"))
                if fs == "FAT32" and self.iso_info["wim_size"] > FAT_MAX and not wimlib:
                    return messagebox.showerror(self.t("start"), self.t("e_wimlib"))
            else:
                if os.path.getsize(self.iso_path) > disk["size"]:
                    return messagebox.showerror(self.t("start"), self.t("e_toobig", img=hsize(os.path.getsize(self.iso_path)), disk=hsize(disk["size"])))
            body = self.t("confirm_body", dev=f"{disk['name']} ({disk['id']}) [{hsize(disk['size'])}]")
            if win and fs == "exFAT":
                body += self.t("confirm_exfat")
            if not messagebox.askokcancel(self.t("confirm_title"), body, icon="warning"):
                return
            unattend = ""
            if win:
                opts = self.win_dialog()
                if opts is None:
                    return
                unattend = build_unattend(opts, getpass.getuser(), mac_locale_tag())
            jd = tempfile.mkdtemp(prefix="rufuspy-")
            job = {"mode": "win" if win else "dd", "disk": disk["id"], "size": disk["size"],
                   "image": self.iso_path, "label": self.label_var.get(), "fs": fs,
                   "scheme": self.scheme_cb.get(), "verify": bool(self.verify_var.get()),
                   "lang": self.lang, "wimlib": wimlib, "unattend": unattend}
            jf = os.path.join(jd, "job.json")
            with open(jf, "w") as f:
                json.dump(job, f)
            self.job = {"dir": jd, "t0": time.time(), "auth": True, "off": 0}
            self.log_lines.clear()
            if self.logtext is not None:
                self.logtext.delete("1.0", "end")
            self.t_start = time.time()
            self.set_busy(True)
            self.bar.set(0, self.t("w_start"), GREEN)
            self.bg(self._launch, jf, jd)
            self.root.after(300, self._poll)

        def _launch(self, jf, jd):
            if getattr(sys, "frozen", False):  # empaquetado como .app
                prog = shlex.quote(sys.executable)
            else:
                prog = f"{shlex.quote(sys.executable)} {shlex.quote(os.path.abspath(__file__))}"
            cmd = f"{prog} --worker {shlex.quote(jf)} >{shlex.quote(jd + '/worker.out')} 2>&1 &"
            esc = cmd.replace("\\", "\\\\").replace('"', '\\"')
            r = subprocess.run(["osascript", "-e", f'do shell script "{esc}" with administrator privileges'],
                               capture_output=True, text=True)
            self.q.put((self._auth_done, (r.returncode, r.stderr.strip())))

        def _auth_done(self, rc, err):
            if not self.job:
                return
            if rc != 0:
                if "-128" in err or "cancel" in err.lower():
                    self.finish("cancelled", self.t("auth_cancel"), quiet=True)
                else:
                    self.finish("error", self.t("auth_fail", e=err))
            else:
                self.job["auth"] = False
                self.job["t0"] = time.time()

        def _poll(self):
            if not self.job:
                return
            jd = self.job["dir"]
            try:
                with open(os.path.join(jd, "log.txt")) as f:
                    f.seek(self.job["off"])
                    data = f.read()
                    self.job["off"] = f.tell()
                for line in data.splitlines():
                    self.log(line)
            except OSError:
                pass
            st = None
            try:
                with open(os.path.join(jd, "progress.json")) as f:
                    st = json.load(f)
            except (OSError, ValueError):
                pass
            if st:
                if st["state"] == "running":
                    self.bar.set(st["pct"], st["text"], GREEN)
                    try:
                        os.kill(st["pid"], 0)
                    except ProcessLookupError:
                        return self.finish("error", self.t("worker_died", e=self._worker_out()))
                    except PermissionError:
                        pass
                else:
                    return self.finish(st["state"], st["text"])
            elif not self.job["auth"] and time.time() - self.job["t0"] > 40:
                return self.finish("error", self.t("no_worker") + "\n" + self._worker_out())
            self.root.after(300, self._poll)

        def _worker_out(self):
            try:
                with open(os.path.join(self.job["dir"], "worker.out")) as f:
                    return f.read()[-600:]
            except OSError:
                return ""

        def finish(self, state, text, quiet=False):
            jd = self.job["dir"] if self.job else None
            if self.job:
                self.log(text)
            self.job = None
            self.set_busy(False)
            self.timer.configure(text=self.timer.cget("text"))
            self.set_bar_key({"done": "done", "cancelled": "cancelled"}.get(state, "error"))
            if jd:
                shutil.rmtree(jd, ignore_errors=True)
            if not quiet:
                if state == "done":
                    messagebox.showinfo(self.t("done"), self.t("done_msg"))
                elif state == "error":
                    messagebox.showerror(self.t("error"), text)
            self.refresh()

        def on_close(self):
            if self.busy:
                messagebox.showwarning(self.t("close"), self.t("busy_close"))
                return
            self.root.destroy()

        def run(self):
            self.root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--worker":
        worker_main(sys.argv[2])
        sys.exit(0)
    if sys.platform != "darwin":
        print("RufusPy esta pensado para macOS.")
        sys.exit(1)
    if tk is None:
        print("Falta Tkinter. Instala Python desde python.org o ejecuta: brew install python-tk")
        sys.exit(1)
    App().run()
