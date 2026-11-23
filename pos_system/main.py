"""Application entry point."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from pos.gui import POSApplication
from pos.repository import JsonRepository, RepositoryError
from pos.service import PosService


def main() -> int:
    application_directory = Path(__file__).resolve().parent
    data_path = application_directory / "data" / "pos_data.json"
    repository = JsonRepository(data_path)

    try:
        service = PosService(repository)
    except (RepositoryError, ValueError) as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Point of Sale",
            f"The application data could not be loaded.\n\n{exc}",
            parent=root,
        )
        root.destroy()
        return 1

    app = POSApplication(service)
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
