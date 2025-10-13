#!/usr/bin/env python3
# gui_tk.py: Define how the GUI looks like and its functionalities, using Tkinter.
# Copyright (C) <2025>  <Zihan Wang>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import base64
import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable


class TkGui:
    """
    A lightweight Tkinter GUI that mirrors the core controls and telemetry display of the PySimpleGUI version.

    Callbacks expected to be assigned by the controller after construction:
      - cb_ext_dev(plr1_on: bool, plr2_on: bool, strobe_light_on: bool, arm_light_on: bool) -> None
      - cb_takeoff_land(mode: str, height_text: str) -> None  # mode one of: standby|takeoff|land|rth
      - cb_gimbal(roll: int, pitch: int, yaw: int) -> None
      - cb_photo() -> None
      - cb_record() -> None
      - cb_stop_record() -> None
      - cb_close() -> None
    """

    def __init__(self, title: str = "SplashDrone 4 GUI"):
        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry("1200x800")

        # Controller callbacks (set by controller)
        self.cb_ext_dev: Optional[Callable] = None
        self.cb_takeoff_land: Optional[Callable] = None
        self.cb_gimbal: Optional[Callable] = None
        self.cb_photo: Optional[Callable] = None
        self.cb_record: Optional[Callable] = None
        self.cb_stop_record: Optional[Callable] = None
        self.cb_close: Optional[Callable] = None

        # Widgets and variables
        self.widgets = {}
        self.vars = {}
        self._img_tk = None  # keep reference to avoid GC

        self.header_font = ("Helvetica", 13, "bold")

        self._build_layout()

        # Defaults
        self.set_camera_status("")
        self.set_record_button_enabled(True)

        # Close protocol
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- Public update helpers ----------
    def set_label_text(self, key: str, text: str):
        if key in self.widgets:
            self.widgets[key].configure(text=text)

    def update_fly_report(self, fr):
        self.set_label_text("-ROLL-", f"{fr.ATTRoll:0.1f}")
        self.set_label_text("-PITCH-", f"{fr.ATTPitch:0.1f}")
        self.set_label_text("-YAW-", f"{fr.ATTYaw:0.1f}")
        self.set_label_text("-LAT-", f"{fr.Lat}")
        self.set_label_text("-LON-", f"{fr.Lon}")
        self.set_label_text("-ALT-", f"{fr.Altitude:0.1f}")
        self.set_label_text("-GPS-HEAD-", f"{fr.GpsHead:0.1f}")
        self.set_label_text("-HS-", f"{fr.FlySpeed:0.2f}")
        self.set_label_text("-VS-", f"{fr.VSpeed:0.2f}")
        self.set_label_text("-THROTTLE-", f"{fr.InGas}")
        self.set_label_text("-GPS-", f"{fr.GpsNum}")
        self.set_label_text("-FLYTIME-", f"{int(fr.FlyTime_Sec)}")

    def update_battery_report(self, br):
        self.set_label_text("-BAT_VOLT-", f"{br.Voltage:0.1f}")
        self.set_label_text("-BAT_REM_CAP-", f"{int(br.RemainCap)}")
        self.set_label_text("-BAT_REM_PER-", f"{int(br.Percent)}")
        self.set_label_text("-BAT_REM_TIME-", f"{int(br.RemainHoverTime)}")
        self.set_label_text("-BAT_TEMP-", f"{int(br.temperature)}")

    def update_gimbal_report(self, gr):
        self.set_label_text("-GIMBAL_ROLL-", f"{gr.roll:0.1f}")
        self.set_label_text("-GIMBAL_PITCH-", f"{gr.pitch:0.1f}")
        self.set_label_text("-GIMBAL_YAW-", f"{gr.yaw:0.1f}")

    def update_gimbal_control(self, gc):
        self.vars["-GIMBAL_SET_ROLL-"].set(int(gc.roll))
        self.vars["-GIMBAL_SET_PITCH-"].set(int(gc.pitch))
        self.vars["-GIMBAL_SET_YAW-"].set(int(gc.yaw))
        # keep numeric labels in sync
        self._set_gimbal_val_label("-GIMBAL_SET_ROLL-")
        self._set_gimbal_val_label("-GIMBAL_SET_PITCH-")
        self._set_gimbal_val_label("-GIMBAL_SET_YAW-")

    def set_camera_status(self, text: str):
        self.set_label_text("-CAMERA_STATUS-", text)

    def set_record_button_enabled(self, enabled: bool):
        state = tk.NORMAL if enabled else tk.DISABLED
        self.widgets["-RECORD-"].configure(state=state)

    def set_image_bytes(self, imgbytes: bytes):
        if not imgbytes:
            return
        label = self.widgets.get("-IMAGE-")
        if label is None:
            return
        # Prefer PIL if available (more robust), else fall back to Tk PhotoImage with PPM data
        try:
            from PIL import Image, ImageTk  # type: ignore
            import io as _io  # local import to avoid global dependency when PIL absent
            try:
                img = Image.open(_io.BytesIO(imgbytes))
                # Optionally, we could resize to fit available space; keep original for now
                self._img_tk = ImageTk.PhotoImage(image=img)
                label.configure(image=self._img_tk)
                label.image = self._img_tk  # pin ref on widget as well
                return
            except Exception:
                pass
        except Exception:
            pass
        # Fallback: use Tk native PPM reader via base64
        try:
            b64 = base64.b64encode(imgbytes).decode("ascii")
            self._img_tk = tk.PhotoImage(data=b64, format="PPM")
            label.configure(image=self._img_tk)
            label.image = self._img_tk  # pin ref on widget as well
        except Exception:
            pass

    # ---------- App loop helpers ----------
    def after(self, ms: int, func: Callable):
        self.root.after(ms, func)

    def mainloop(self):
        self.root.mainloop()

    # ---------- Internal UI builders ----------
    def _section(self, parent, title):
        frm = ttk.Frame(parent)
        ttk.Label(frm, text=title, font=self.header_font, anchor="center").pack(side=tk.TOP, fill=tk.X, pady=(0, 6))
        return frm

    def _kv_row(self, parent, label_text, key):
        row = ttk.Frame(parent)
        ttk.Label(row, text=label_text, width=18).pack(side=tk.LEFT)
        val_lbl = ttk.Label(row, text="", width=18)
        val_lbl.pack(side=tk.LEFT)
        self.widgets[key] = val_lbl
        row.pack(anchor="w", padx=4, pady=1)

    def _build_status_columns(self, parent):
        # Column 1: Flight
        col1 = ttk.Frame(parent)
        s1 = self._section(col1, "Flight Status")
        for label_text, key in [
            ("Roll (deg)", "-ROLL-"),
            ("Pitch (deg)", "-PITCH-"),
            ("Yaw (deg)", "-YAW-"),
            ("Latitude", "-LAT-"),
            ("Longitude", "-LON-"),
            ("Altitude (m)", "-ALT-"),
            ("GPS-HEAD", "-GPS-HEAD-"),
            ("HSpeed (m/s)", "-HS-"),
            ("VSpeed (m/s)", "-VS-"),
            ("Throttle (0-100)", "-THROTTLE-"),
            ("nGPS", "-GPS-"),
            ("Fly Time (s)", "-FLYTIME-"),
        ]:
            self._kv_row(s1, label_text, key)
        s1.pack(fill=tk.X)
        col1.grid(row=0, column=0, sticky="nwe")

        # Column 2: Battery + Gimbal report
        col2 = ttk.Frame(parent)
        s2 = self._section(col2, "Battery Status")
        for label_text, key in [
            ("Voltage (V)", "-BAT_VOLT-"),
            ("Remaining Cap (mAh)", "-BAT_REM_CAP-"),
            ("Remaining Percentage (%)", "-BAT_REM_PER-"),
            ("Remaining Hover Time (min)", "-BAT_REM_TIME-"),
            ("Temperature (Cel)", "-BAT_TEMP-"),
        ]:
            self._kv_row(s2, label_text, key)
        s2.pack(fill=tk.X)

        s3 = self._section(col2, "Gimbal Status")
        for label_text, key in [
            ("Roll (deg)", "-GIMBAL_ROLL-"),
            ("Pitch (deg)", "-GIMBAL_PITCH-"),
            ("Yaw (deg)", "-GIMBAL_YAW-"),
        ]:
            self._kv_row(s3, label_text, key)
        s3.pack(fill=tk.X)
        col2.grid(row=0, column=1, sticky="nwe", padx=10)

        # Column 3: Video
        col3 = ttk.Frame(parent)
        s4 = self._section(col3, "Video Streaming")
        img_lbl = ttk.Label(s4)
        img_lbl.pack()
        s4.pack(fill=tk.BOTH, expand=True)
        col3.grid(row=0, column=2, sticky="nwe")

        self.widgets["-IMAGE-"] = img_lbl

        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_columnconfigure(2, weight=1)

    def _build_controls_row(self, parent):
        # Payload & LED
        pl = self._section(parent, "Payload Release & LED")
        self.vars["-PLR1-"] = tk.BooleanVar(value=False)
        self.vars["-PLR2-"] = tk.BooleanVar(value=False)
        self.vars["-STROBE_LED-"] = tk.BooleanVar(value=True)
        self.vars["-ARM_LED-"] = tk.BooleanVar(value=True)
        for text, key in [
            ("Payload Release 1", "-PLR1-"),
            ("Payload Release 2", "-PLR2-"),
            ("Strobe Light", "-STROBE_LED-"),
            ("Arm Light", "-ARM_LED-"),
        ]:
            ttk.Checkbutton(pl, text=text, variable=self.vars[key],
                            command=self._on_ext_dev_changed).pack(side=tk.LEFT, padx=4)
        pl.grid(row=0, column=0, sticky="w")

        # Takeoff/Land/RTH
        tl = self._section(parent, "Takeoff & Land")
        self.vars["TAKE_MODE"] = tk.StringVar(value="standby")
        for text, value in [("Standby", "standby"), ("Takeoff", "takeoff"),
                            ("Land", "land"), ("RTH", "rth")]:
            ttk.Radiobutton(tl, text=text, value=value, variable=self.vars["TAKE_MODE"],
                            command=self._on_takeoff_land_changed).pack(side=tk.LEFT, padx=4)
        ttk.Label(tl, text="Height (m)").pack(side=tk.LEFT, padx=(10, 2))
        self.vars["-TAKEOFF_HEIGHT-"] = tk.StringVar(value="0.4")
        ttk.Entry(tl, textvariable=self.vars["-TAKEOFF_HEIGHT-"], width=6).pack(side=tk.LEFT)
        tl.grid(row=0, column=1, sticky="w", padx=10)

        # Gimbal control
        gb = self._section(parent, "Gimbal Control")
        self.vars["-GIMBAL_SET_ROLL-"] = tk.IntVar(value=0)
        self.vars["-GIMBAL_SET_PITCH-"] = tk.IntVar(value=0)
        self.vars["-GIMBAL_SET_YAW-"] = tk.IntVar(value=0)
        self._scale(gb, "Roll", "-GIMBAL_SET_ROLL-", -45, 45)
        self._scale(gb, "Pitch", "-GIMBAL_SET_PITCH-", -90, 90)
        self._scale(gb, "Yaw", "-GIMBAL_SET_YAW-", -45, 45)
        ttk.Button(gb, text="Reset", command=self._on_gimbal_reset).pack(anchor="w", pady=4)
        gb.grid(row=0, column=2, sticky="w", padx=10)

        # Camera control
        cam = self._section(parent, "Camera Control")
        ttk.Button(cam, text="Take Photo", command=self._on_photo).pack(side=tk.LEFT, padx=4)
        btn_record = ttk.Button(cam, text="Record", command=self._on_record)
        btn_record.pack(side=tk.LEFT, padx=4)
        ttk.Button(cam, text="Stop Recording", command=self._on_stop_record).pack(side=tk.LEFT, padx=4)
        status_lbl = ttk.Label(cam, text="", width=30, anchor="w")
        status_lbl.pack(side=tk.LEFT, padx=10)
        cam.grid(row=0, column=3, sticky="w", padx=10)

        self.widgets["-RECORD-"] = btn_record
        self.widgets["-CAMERA_STATUS-"] = status_lbl

        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_columnconfigure(2, weight=1)
        parent.grid_columnconfigure(3, weight=1)

    def _scale(self, parent, label, key, vmin, vmax):
        frm = ttk.Frame(parent)
        ttk.Label(frm, text=f"{label} ").pack(side=tk.LEFT)
        # value label showing the exact set value
        val_lbl = ttk.Label(frm, text=str(self.vars[key].get()), width=4)
        # define live update callback
        def _on_slide(v: str, _key=key, _lbl=val_lbl):
            try:
                _lbl.configure(text=str(int(float(v))))
            except Exception:
                _lbl.configure(text=str(v))
        sc = ttk.Scale(frm, from_=vmin, to=vmax, orient="horizontal",
                       command=_on_slide,
                       variable=self.vars[key])
        sc.pack(side=tk.LEFT, fill=tk.X, expand=True)
        sc.bind("<ButtonRelease-1>", lambda e: self._on_gimbal_release())
        val_lbl.pack(side=tk.LEFT, padx=4)
        # store label widget for programmatic updates later
        self.widgets[f"{key}-VAL"] = val_lbl
        frm.pack(fill=tk.X, pady=2)

    def _build_layout(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.BOTH, expand=True)

        status_row = ttk.Frame(top)
        status_row.pack(fill=tk.X, pady=(0, 8))
        self._build_status_columns(status_row)

        ttk.Separator(top, orient="horizontal").pack(fill=tk.X, pady=6)

        controls_row = ttk.Frame(top)
        controls_row.pack(fill=tk.X)
        self._build_controls_row(controls_row)

        ttk.Separator(top, orient="horizontal").pack(fill=tk.X, pady=6)

    # ---------- Internal event dispatchers ----------
    def _on_ext_dev_changed(self):
        if self.cb_ext_dev:
            self.cb_ext_dev(
                plr1_on=self.vars["-PLR1-"].get(),
                plr2_on=self.vars["-PLR2-"].get(),
                strobe_light_on=self.vars["-STROBE_LED-"].get(),
                arm_light_on=self.vars["-ARM_LED-"].get(),
            )

    def _on_takeoff_land_changed(self):
        if self.cb_takeoff_land:
            self.cb_takeoff_land(
                mode=self.vars["TAKE_MODE"].get(),
                height_text=self.vars["-TAKEOFF_HEIGHT-"].get(),
            )

    def _on_gimbal_release(self):
        if self.cb_gimbal:
            self.cb_gimbal(
                roll=int(self.vars["-GIMBAL_SET_ROLL-"].get()),
                pitch=int(self.vars["-GIMBAL_SET_PITCH-"].get()),
                yaw=int(self.vars["-GIMBAL_SET_YAW-"].get()),
            )

    def _on_gimbal_reset(self):
        self.vars["-GIMBAL_SET_ROLL-"].set(0)
        self.vars["-GIMBAL_SET_PITCH-"].set(0)
        self.vars["-GIMBAL_SET_YAW-"].set(0)
        # update numeric labels
        self._set_gimbal_val_label("-GIMBAL_SET_ROLL-")
        self._set_gimbal_val_label("-GIMBAL_SET_PITCH-")
        self._set_gimbal_val_label("-GIMBAL_SET_YAW-")
        if self.cb_gimbal:
            self.cb_gimbal(roll=0, pitch=0, yaw=0)

    def _on_photo(self):
        if self.cb_photo:
            self.cb_photo()

    def _on_record(self):
        if self.cb_record:
            self.cb_record()

    def _on_stop_record(self):
        if self.cb_stop_record:
            self.cb_stop_record()

    def _on_close(self):
        if self.cb_close:
            self.cb_close()
        self.root.destroy()

    def _set_gimbal_val_label(self, key: str):
        lbl = self.widgets.get(f"{key}-VAL")
        if not lbl:
            return
        try:
            lbl.configure(text=str(int(self.vars[key].get())))
        except Exception:
            lbl.configure(text=str(self.vars[key].get()))
