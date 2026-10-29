#!/usr/bin/env python3
import re
import signal
import subprocess
import threading
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox
from tkinter import ttk


VALUE_RE = re.compile(r"^(?P<type>.+?) value is:\s*(?P<value>.*)$")


@dataclass
class ParamInfo:
    name: str
    type_text: str
    current_value: str


class Ros2ParamClient:
    def __init__(self, timeout_sec: float = 10.0):
        self.timeout_sec = max(1.0, float(timeout_sec))
        self.process_timeout_sec = self.timeout_sec + 3.0

    def _run(self, args):
        completed = None
        for attempt in range(2):
            try:
                completed = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=self.process_timeout_sec,
                )
                break
            except subprocess.TimeoutExpired:
                if attempt == 1:
                    raise RuntimeError(
                        f"Command timeout ({self.process_timeout_sec:.1f}s): {' '.join(args)}"
                    )
        if completed is None:
            raise RuntimeError(f"Command failed: {' '.join(args)}")
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        if completed.returncode != 0:
            output = "\n".join(x for x in [stdout, stderr] if x).strip()
            raise RuntimeError(output or f"Command failed: {' '.join(args)}")
        return stdout

    def list_params(self, node_name: str):
        output = self._run(["ros2", "param", "list", node_name])
        params = []
        for line in output.splitlines():
            text = line.strip()
            if not text:
                continue
            if text.endswith(":"):
                continue
            if text.startswith("/"):
                continue
            if text.startswith("WARNING"):
                continue
            params.append(text)
        return sorted(set(params))

    def get_param(self, node_name: str, param_name: str):
        output = self._run(
            [
                "ros2",
                "param",
                "get",
                "--timeout",
                str(int(self.timeout_sec)),
                node_name,
                param_name,
            ]
        )
        for line in output.splitlines():
            text = line.strip()
            match = VALUE_RE.match(text)
            if match:
                return match.group("type"), match.group("value")
        return "Unknown", output.strip()

    def set_param(self, node_name: str, param_name: str, value: str):
        return self._run(
            [
                "ros2",
                "param",
                "set",
                "--timeout",
                str(int(self.timeout_sec)),
                node_name,
                param_name,
                value,
            ]
        )


class ParamRow:
    def __init__(self, name, type_var, current_var, input_var, status_var):
        self.name = name
        self.type_var = type_var
        self.current_var = current_var
        self.input_var = input_var
        self.status_var = status_var


class ParamUiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ROS2 Param UI")
        self.root.geometry("1200x720")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.client = Ros2ParamClient(timeout_sec=10)
        self.rows = {}
        self.refresh_button: ttk.Button
        self.set_all_button: ttk.Button
        self.closing = False
        self._exit_signal = None

        self.node_var = tk.StringVar(value="/controller_server")
        self.status_var = tk.StringVar(value="Ready")

        self._build_ui()
        self._install_signal_handlers()

    def _install_signal_handlers(self):
        def handle_signal(signum, _frame):
            self._exit_signal = signum

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, handle_signal)
            except (ValueError, OSError):
                pass

        self._poll_exit_signal()

    def _poll_exit_signal(self):
        if self.closing:
            return
        if self._exit_signal is not None:
            self.status_var.set("Interrupt received, shutting down...")
            self.on_close()
            return
        self.root.after(100, self._poll_exit_signal)

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Node:").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.node_var, width=36).pack(side=tk.LEFT, padx=(6, 12))

        self.refresh_button = ttk.Button(top, text="Refresh Params", command=self.refresh_params)
        self.refresh_button.pack(side=tk.LEFT)

        self.set_all_button = ttk.Button(top, text="Set All Changed", command=self.set_all_changed)
        self.set_all_button.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(self.root, textvariable=self.status_var, padding=(10, 2)).pack(fill=tk.X)

        container = ttk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self.canvas = tk.Canvas(container, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.rows_frame = ttk.Frame(self.canvas)
        self.rows_window = self.canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.rows_frame.bind("<Configure>", self._on_rows_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_rows_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self.rows_window, width=event.width)

    def _set_busy(self, busy: bool):
        state = tk.DISABLED if busy else tk.NORMAL
        self.refresh_button.configure(state=state)
        self.set_all_button.configure(state=state)

    def _run_background(self, fn, on_done=None, on_error=None):
        def worker():
            try:
                result = fn()
            except Exception as exc:
                if on_error is not None:
                    error_cb = on_error
                    error_msg = str(exc)
                    self._safe_after(lambda cb=error_cb, msg=error_msg: cb(msg))
                return
            if on_done is not None:
                done_cb = on_done
                self._safe_after(lambda cb=done_cb, res=result: cb(res))

        threading.Thread(target=worker, daemon=True).start()

    def _safe_after(self, callback):
        if self.closing:
            return
        try:
            self.root.after(0, callback)
        except (RuntimeError, tk.TclError):
            pass

    def on_close(self):
        if self.closing:
            return
        self.closing = True
        try:
            self.root.quit()
            self.root.destroy()
        except tk.TclError:
            pass

    def _clear_rows(self):
        for widget in self.rows_frame.winfo_children():
            widget.destroy()
        self.rows.clear()

    def _build_header(self):
        headers = ["Parameter", "Type", "Current Value", "New Value", "Action", "Status"]
        for col, text in enumerate(headers):
            lbl = ttk.Label(self.rows_frame, text=text)
            lbl.grid(row=0, column=col, sticky="w", padx=6, pady=(4, 6))

        self.rows_frame.grid_columnconfigure(0, weight=2)
        self.rows_frame.grid_columnconfigure(1, weight=1)
        self.rows_frame.grid_columnconfigure(2, weight=3)
        self.rows_frame.grid_columnconfigure(3, weight=3)
        self.rows_frame.grid_columnconfigure(4, weight=0)
        self.rows_frame.grid_columnconfigure(5, weight=2)

    def _rebuild_rows(self, params):
        self._clear_rows()
        self._build_header()

        for idx, info in enumerate(params, start=1):
            type_var = tk.StringVar(value=info.type_text)
            current_var = tk.StringVar(value=info.current_value)
            input_var = tk.StringVar(value=info.current_value)
            status_var = tk.StringVar(value="")

            ttk.Label(self.rows_frame, text=info.name).grid(
                row=idx, column=0, sticky="w", padx=6, pady=2
            )
            ttk.Label(self.rows_frame, textvariable=type_var).grid(
                row=idx, column=1, sticky="w", padx=6, pady=2
            )
            ttk.Label(self.rows_frame, textvariable=current_var).grid(
                row=idx, column=2, sticky="w", padx=6, pady=2
            )
            ttk.Entry(self.rows_frame, textvariable=input_var).grid(
                row=idx, column=3, sticky="ew", padx=6, pady=2
            )

            ttk.Button(
                self.rows_frame,
                text="Set",
                command=lambda n=info.name: self.set_single_param(n),
            ).grid(row=idx, column=4, sticky="w", padx=6, pady=2)

            ttk.Label(self.rows_frame, textvariable=status_var).grid(
                row=idx, column=5, sticky="w", padx=6, pady=2
            )

            self.rows[info.name] = ParamRow(
                name=info.name,
                type_var=type_var,
                current_var=current_var,
                input_var=input_var,
                status_var=status_var,
            )

    def _load_all_params(self, node_name: str):
        names = self.client.list_params(node_name)
        infos = []
        for name in names:
            type_text, value = self.client.get_param(node_name, name)
            infos.append(ParamInfo(name=name, type_text=type_text, current_value=value))
        return infos

    def refresh_params(self):
        if self.closing:
            return
        node_name = self.node_var.get().strip()
        if not node_name:
            messagebox.showerror("Invalid Node", "Node name cannot be empty")
            return

        self.status_var.set(f"Loading parameters from {node_name} ...")
        self._set_busy(True)

        def done(infos):
            self._set_busy(False)
            self._rebuild_rows(infos)
            self.status_var.set(f"Loaded {len(infos)} parameters from {node_name}")

        def error(msg):
            self._set_busy(False)
            self.status_var.set("Load failed")
            messagebox.showerror("Refresh Failed", msg)

        self._run_background(lambda: self._load_all_params(node_name), on_done=done, on_error=error)

    def set_single_param(self, param_name: str):
        if self.closing:
            return
        row = self.rows.get(param_name)
        if row is None:
            return

        node_name = self.node_var.get().strip()
        if not node_name:
            messagebox.showerror("Invalid Node", "Node name cannot be empty")
            return

        new_value = row.input_var.get()
        row.status_var.set("setting...")

        def work():
            set_out = self.client.set_param(node_name, param_name, new_value)
            type_text, current = self.client.get_param(node_name, param_name)
            return set_out, type_text, current

        def done(result):
            set_out, type_text, current = result
            row.type_var.set(type_text)
            row.current_var.set(current)
            row.input_var.set(current)
            if "successful" in set_out.lower():
                row.status_var.set("ok")
            else:
                row.status_var.set(set_out)
            self.status_var.set(f"Set parameter: {param_name}")

        def error(msg):
            row.status_var.set("failed")
            self.status_var.set(f"Set failed: {param_name}")
            messagebox.showerror("Set Failed", f"{param_name}\n\n{msg}")

        self._run_background(work, on_done=done, on_error=error)

    def set_all_changed(self):
        if self.closing:
            return
        node_name = self.node_var.get().strip()
        if not node_name:
            messagebox.showerror("Invalid Node", "Node name cannot be empty")
            return

        changed = []
        for name, row in self.rows.items():
            if row.input_var.get() != row.current_var.get():
                changed.append((name, row.input_var.get()))

        if not changed:
            self.status_var.set("No changed parameters")
            return

        for name, _ in changed:
            self.rows[name].status_var.set("queued")

        self.status_var.set(f"Setting {len(changed)} parameters ...")
        self._set_busy(True)

        def work():
            results = []
            for name, value in changed:
                try:
                    out = self.client.set_param(node_name, name, value)
                    type_text, current = self.client.get_param(node_name, name)
                    results.append((name, True, out, type_text, current))
                except Exception as exc:
                    results.append((name, False, str(exc), "", ""))
            return results

        def done(results):
            self._set_busy(False)
            ok_count = 0
            fail_count = 0
            for name, ok, out, type_text, current in results:
                row = self.rows.get(name)
                if row is None:
                    continue
                if ok:
                    ok_count += 1
                    row.type_var.set(type_text)
                    row.current_var.set(current)
                    row.input_var.set(current)
                    row.status_var.set("ok")
                else:
                    fail_count += 1
                    row.status_var.set("failed")
                    if out:
                        row.status_var.set(out.splitlines()[-1][:60])
            self.status_var.set(f"Set done: {ok_count} ok, {fail_count} failed")

        def error(msg):
            self._set_busy(False)
            self.status_var.set("Set failed")
            messagebox.showerror("Set All Failed", msg)

        self._run_background(work, on_done=done, on_error=error)


def main():
    root = tk.Tk()
    app = ParamUiApp(root)
    app.refresh_params()
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.on_close()


if __name__ == "__main__":
    main()
