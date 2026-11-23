"""Tkinter desktop interface for the supermarket POS."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .models import (
    PosError,
    Product,
    ReturnTransaction,
    SaleDraft,
    SaleTransaction,
    ValidationError,
    as_money,
    format_money,
)
from .receipts import (
    build_return_receipt,
    build_sale_receipt,
    save_receipt,
)
from .service import PosService


BACKGROUND = "#eef2f5"
CARD = "#ffffff"
TEXT = "#17212b"
MUTED = "#65717d"
ACCENT = "#0f766e"
ACCENT_ACTIVE = "#115e59"
BLUE = "#1d4ed8"
RED = "#b91c1c"
HEADER = "#102a43"


class ReceiptWindow(tk.Toplevel):
    """Read-only receipt viewer with clipboard support."""

    def __init__(self, parent: tk.Misc, title: str, content: str, path: Path) -> None:
        super().__init__(parent)
        self.title(title)
        self.geometry("570x650")
        self.minsize(470, 480)
        self.configure(bg=CARD)
        self.transient(parent)

        body = ttk.Frame(self, style="Card.TFrame", padding=18)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=title, style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            body,
            text=f"Saved to: {path}",
            style="Muted.TLabel",
            wraplength=500,
        ).pack(anchor="w", pady=(4, 12))

        text_frame = ttk.Frame(body, style="Card.TFrame")
        text_frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")
        self.text = tk.Text(
            text_frame,
            wrap="none",
            font=("Consolas", 10),
            bg="#f8fafc",
            fg=TEXT,
            relief="solid",
            borderwidth=1,
            padx=12,
            pady=12,
            yscrollcommand=scrollbar.set,
        )
        self.text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.text.yview)
        self.text.insert("1.0", content)
        self.text.config(state="disabled")

        controls = ttk.Frame(body, style="Card.TFrame")
        controls.pack(fill="x", pady=(14, 0))
        ttk.Button(
            controls,
            text="Copy",
            style="Secondary.TButton",
            command=lambda: self._copy(content),
        ).pack(side="left")
        ttk.Button(
            controls,
            text="Close",
            style="Primary.TButton",
            command=self.destroy,
        ).pack(side="right")

    def _copy(self, content: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(content)
        messagebox.showinfo("Copied", "The receipt was copied to the clipboard.", parent=self)


class POSApplication(tk.Tk):
    """Main application window."""

    def __init__(self, service: PosService) -> None:
        super().__init__()
        self.service = service
        self.draft: SaleDraft = service.new_sale()
        self.return_sale_id: str | None = None
        self.receipt_directory = service.repository.path.parent / "receipts"

        self.title("Cornerstone Market - Point of Sale")
        self.geometry("1180x760")
        self.minsize(980, 650)
        self.configure(bg=BACKGROUND)

        self._configure_styles()
        self._build_header()
        self._build_tabs()
        self._build_status_bar()
        self.refresh_all()
        self.sale_barcode.focus_set()

        self.bind("<F2>", lambda _event: self._complete_sale())
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure(".", font=("Segoe UI", 10), foreground=TEXT)
        style.configure("App.TFrame", background=BACKGROUND)
        style.configure("Header.TFrame", background=HEADER)
        style.configure("Card.TFrame", background=CARD)
        style.configure("Card.TLabel", background=CARD, foreground=TEXT)
        style.configure(
            "CardTitle.TLabel",
            background=CARD,
            foreground=TEXT,
            font=("Segoe UI Semibold", 15),
        )
        style.configure(
            "Section.TLabel",
            background=CARD,
            foreground=MUTED,
            font=("Segoe UI Semibold", 10),
        )
        style.configure("Muted.TLabel", background=CARD, foreground=MUTED)
        style.configure(
            "Total.TLabel",
            background=CARD,
            foreground=TEXT,
            font=("Segoe UI Semibold", 28),
        )
        style.configure(
            "Header.TLabel",
            background=HEADER,
            foreground="#ffffff",
            font=("Segoe UI Semibold", 20),
        )
        style.configure(
            "HeaderMuted.TLabel",
            background=HEADER,
            foreground="#bcccdc",
            font=("Segoe UI", 9),
        )
        style.configure(
            "Primary.TButton",
            background=ACCENT,
            foreground="#ffffff",
            padding=(15, 9),
            borderwidth=0,
        )
        style.map(
            "Primary.TButton",
            background=[("active", ACCENT_ACTIVE), ("disabled", "#9ca3af")],
        )
        style.configure(
            "Secondary.TButton",
            background="#e4e9ee",
            foreground=TEXT,
            padding=(13, 8),
            borderwidth=0,
        )
        style.map("Secondary.TButton", background=[("active", "#d5dde5")])
        style.configure(
            "Danger.TButton",
            background="#fee2e2",
            foreground=RED,
            padding=(13, 8),
            borderwidth=0,
        )
        style.map("Danger.TButton", background=[("active", "#fecaca")])
        style.configure(
            "TNotebook",
            background=BACKGROUND,
            borderwidth=0,
            tabmargins=(0, 8, 0, 0),
        )
        style.configure(
            "TNotebook.Tab",
            background="#dbe2e8",
            foreground=MUTED,
            padding=(20, 10),
            font=("Segoe UI Semibold", 10),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", CARD), ("active", "#e9eef2")],
            foreground=[("selected", ACCENT)],
        )
        style.configure(
            "Treeview",
            background=CARD,
            fieldbackground=CARD,
            foreground=TEXT,
            rowheight=29,
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background="#e8edf1",
            foreground=TEXT,
            padding=(8, 8),
            font=("Segoe UI Semibold", 9),
        )
        style.map("Treeview", background=[("selected", "#cfe9e6")])
        style.configure("TEntry", padding=7)
        style.configure("TCombobox", padding=6)
        style.configure("TSpinbox", padding=6)

    def _build_header(self) -> None:
        header = ttk.Frame(self, style="Header.TFrame", padding=(28, 18))
        header.pack(fill="x")
        title_group = ttk.Frame(header, style="Header.TFrame")
        title_group.pack(side="left")
        ttk.Label(
            title_group,
            text="CORNERSTONE MARKET",
            style="Header.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            title_group,
            text="Sales, returns, and inventory in one workspace",
            style="HeaderMuted.TLabel",
        ).pack(anchor="w", pady=(3, 0))
        ttk.Label(
            header,
            text="POINT OF SALE",
            style="HeaderMuted.TLabel",
        ).pack(side="right", anchor="center")

    def _build_tabs(self) -> None:
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=24, pady=(16, 8))

        self.sale_tab = ttk.Frame(self.notebook, style="App.TFrame")
        self.return_tab = ttk.Frame(self.notebook, style="App.TFrame")
        self.inventory_tab = ttk.Frame(self.notebook, style="App.TFrame")
        self.history_tab = ttk.Frame(self.notebook, style="App.TFrame")
        self.notebook.add(self.sale_tab, text="Process Sale")
        self.notebook.add(self.return_tab, text="Handle Returns")
        self.notebook.add(self.inventory_tab, text="Inventory")
        self.notebook.add(self.history_tab, text="Transactions")

        self._build_sale_tab()
        self._build_return_tab()
        self._build_inventory_tab()
        self._build_history_tab()

    def _card(self, parent: tk.Misc) -> ttk.Frame:
        return ttk.Frame(parent, style="Card.TFrame", padding=18)

    def _build_sale_tab(self) -> None:
        content = ttk.Frame(self.sale_tab, style="App.TFrame", padding=(0, 12, 0, 0))
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=2, minsize=340)
        content.rowconfigure(0, weight=1)

        left = self._card(content)
        right = self._card(content)
        left.grid(row=0, column=0, sticky="nsew")
        right.grid(row=0, column=1, sticky="nsew")

        ttk.Label(left, text="New Sale", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            left,
            text="Scan a barcode or choose a product, then set the quantity.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(2, 16))

        scan = ttk.Frame(left, style="Card.TFrame")
        scan.pack(fill="x", pady=(0, 14))
        scan.columnconfigure(0, weight=1)
        self.sale_barcode = ttk.Combobox(scan, textvariable=self._sale_barcode_var())
        self.sale_barcode.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.sale_barcode.bind("<Return>", lambda _event: self._add_sale_item())

        self.sale_quantity = tk.IntVar(value=1)
        quantity = ttk.Spinbox(
            scan,
            from_=1,
            to=999,
            width=6,
            textvariable=self.sale_quantity,
        )
        quantity.grid(row=0, column=1, padx=(0, 8))
        ttk.Button(
            scan,
            text="Add Item",
            style="Primary.TButton",
            command=self._add_sale_item,
        ).grid(row=0, column=2)

        tree_frame = ttk.Frame(left, style="Card.TFrame")
        tree_frame.pack(fill="both", expand=True)
        columns = ("barcode", "product", "qty", "price", "total")
        self.sale_tree = self._tree(tree_frame, columns)
        self.sale_tree.heading("barcode", text="Barcode")
        self.sale_tree.heading("product", text="Product")
        self.sale_tree.heading("qty", text="Qty")
        self.sale_tree.heading("price", text="Unit Price")
        self.sale_tree.heading("total", text="Line Total")
        self.sale_tree.column("barcode", width=130, anchor="w")
        self.sale_tree.column("product", width=220, anchor="w")
        self.sale_tree.column("qty", width=55, anchor="center")
        self.sale_tree.column("price", width=95, anchor="e")
        self.sale_tree.column("total", width=95, anchor="e")
        self.sale_tree.bind("<Delete>", lambda _event: self._remove_sale_item())

        actions = ttk.Frame(left, style="Card.TFrame")
        actions.pack(fill="x", pady=(12, 0))
        ttk.Button(
            actions,
            text="Remove Selected",
            style="Secondary.TButton",
            command=self._remove_sale_item,
        ).pack(side="left")
        ttk.Button(
            actions,
            text="Clear Sale",
            style="Danger.TButton",
            command=self._clear_sale,
        ).pack(side="left", padx=8)

        ttk.Label(right, text="Payment", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(right, text="CASH CHECKOUT", style="Section.TLabel").pack(
            anchor="w", pady=(18, 2)
        )
        self.sale_total_var = tk.StringVar(value="$0.00")
        ttk.Label(right, textvariable=self.sale_total_var, style="Total.TLabel").pack(
            anchor="w"
        )
        self.sale_count_var = tk.StringVar(value="0 items")
        ttk.Label(
            right,
            textvariable=self.sale_count_var,
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 18))

        ttk.Label(right, text="Cash received", style="Card.TLabel").pack(anchor="w")
        self.cash_var = tk.StringVar()
        self.cash_entry = ttk.Entry(right, textvariable=self.cash_var, font=("Segoe UI", 16))
        self.cash_entry.pack(fill="x", pady=(5, 10))
        self.cash_entry.bind("<Return>", lambda _event: self._complete_sale())
        self.cash_entry.bind("<KeyRelease>", lambda _event: self._update_change_preview())

        preview = ttk.Frame(right, style="Card.TFrame")
        preview.pack(fill="x", pady=(0, 16))
        ttk.Label(preview, text="Change", style="Muted.TLabel").pack(side="left")
        self.change_var = tk.StringVar(value="$0.00")
        ttk.Label(
            preview,
            textvariable=self.change_var,
            style="Card.TLabel",
            font=("Segoe UI Semibold", 15),
        ).pack(side="right")

        ttk.Button(
            right,
            text="Complete Sale  [F2]",
            style="Primary.TButton",
            command=self._complete_sale,
        ).pack(fill="x", pady=(0, 8))
        ttk.Button(
            right,
            text="New Sale",
            style="Secondary.TButton",
            command=self._clear_sale,
        ).pack(fill="x")
        ttk.Label(
            right,
            text="A receipt is saved automatically after checkout.",
            style="Muted.TLabel",
            wraplength=290,
        ).pack(anchor="w", pady=(18, 0))

    def _tree(self, parent: ttk.Frame, columns: tuple[str, ...]) -> ttk.Treeview:
        scrollbar = ttk.Scrollbar(parent)
        scrollbar.pack(side="right", fill="y")
        tree = ttk.Treeview(
            parent,
            columns=columns,
            show="headings",
            selectmode="browse",
            yscrollcommand=scrollbar.set,
        )
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=tree.yview)
        return tree

    def _sale_barcode_var(self) -> tk.StringVar:
        self.sale_barcode_var = tk.StringVar()
        return self.sale_barcode_var

    def _build_return_tab(self) -> None:
        card = self._card(self.return_tab)
        card.pack(fill="both", expand=True, pady=(12, 0))
        ttk.Label(card, text="Handle Returns", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            card,
            text="Find the original sale, select a line, and process a full or partial refund.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(2, 16))

        lookup = ttk.Frame(card, style="Card.TFrame")
        lookup.pack(fill="x", pady=(0, 14))
        ttk.Label(lookup, text="Original sale ID", style="Card.TLabel").pack(
            side="left", padx=(0, 10)
        )
        self.return_id_var = tk.StringVar()
        return_entry = ttk.Entry(lookup, textvariable=self.return_id_var)
        return_entry.pack(side="left", fill="x", expand=True)
        return_entry.bind("<Return>", lambda _event: self._lookup_return_sale())
        ttk.Button(
            lookup,
            text="Find Sale",
            style="Primary.TButton",
            command=self._lookup_return_sale,
        ).pack(side="left", padx=(8, 0))

        self.return_sale_summary = tk.StringVar(
            value="Enter a sale ID to see its returnable items."
        )
        ttk.Label(
            card,
            textvariable=self.return_sale_summary,
            style="Muted.TLabel",
            wraplength=900,
        ).pack(anchor="w", pady=(0, 12))

        tree_frame = ttk.Frame(card, style="Card.TFrame")
        tree_frame.pack(fill="both", expand=True)
        columns = ("barcode", "product", "price", "sold", "returned", "remaining")
        self.return_tree = self._tree(tree_frame, columns)
        headings = {
            "barcode": "Barcode",
            "product": "Product",
            "price": "Unit Price",
            "sold": "Sold",
            "returned": "Returned",
            "remaining": "Returnable",
        }
        widths = {
            "barcode": 140,
            "product": 300,
            "price": 100,
            "sold": 75,
            "returned": 85,
            "remaining": 100,
        }
        for column in columns:
            self.return_tree.heading(column, text=headings[column])
            self.return_tree.column(
                column, width=widths[column], anchor="w" if column in {"barcode", "product"} else "center"
            )

        controls = ttk.Frame(card, style="Card.TFrame")
        controls.pack(fill="x", pady=(14, 0))
        ttk.Label(controls, text="Return quantity", style="Card.TLabel").pack(
            side="left", padx=(0, 8)
        )
        self.return_quantity = tk.IntVar(value=1)
        ttk.Spinbox(
            controls,
            from_=1,
            to=999,
            width=7,
            textvariable=self.return_quantity,
        ).pack(side="left")
        ttk.Button(
            controls,
            text="Return Selected Item",
            style="Primary.TButton",
            command=self._return_selected_item,
        ).pack(side="right")

    def _build_inventory_tab(self) -> None:
        content = ttk.Frame(self.inventory_tab, style="App.TFrame", padding=(0, 12, 0, 0))
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=1, minsize=300)
        content.columnconfigure(1, weight=3)
        content.rowconfigure(0, weight=1)

        form = self._card(content)
        table_card = self._card(content)
        form.grid(row=0, column=0, sticky="nsew")
        table_card.grid(row=0, column=1, sticky="nsew")

        ttk.Label(form, text="Inventory", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            form,
            text="Add products, update details, or receive new stock.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(2, 18))

        self.inventory_fields: dict[str, tk.StringVar] = {}
        labels = [
            ("barcode", "Barcode"),
            ("name", "Product name"),
            ("price", "Unit price"),
            ("quantity", "Stock quantity"),
        ]
        for key, label in labels:
            ttk.Label(form, text=label, style="Card.TLabel").pack(anchor="w")
            variable = tk.StringVar()
            self.inventory_fields[key] = variable
            ttk.Entry(form, textvariable=variable).pack(fill="x", pady=(5, 12))

        ttk.Button(
            form,
            text="Add Product",
            style="Primary.TButton",
            command=self._add_product,
        ).pack(fill="x", pady=(2, 7))
        ttk.Button(
            form,
            text="Save Name / Price",
            style="Secondary.TButton",
            command=self._update_product,
        ).pack(fill="x", pady=7)
        ttk.Button(
            form,
            text="Add Entered Quantity to Stock",
            style="Secondary.TButton",
            command=self._restock_product,
        ).pack(fill="x", pady=7)
        ttk.Label(
            form,
            text="Tip: select a product in the table to load its values.",
            style="Muted.TLabel",
            wraplength=270,
        ).pack(anchor="w", pady=(12, 0))

        ttk.Label(table_card, text="Product Catalog", style="CardTitle.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            table_card,
            text="All changes are saved immediately.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(2, 14))
        tree_frame = ttk.Frame(table_card, style="Card.TFrame")
        tree_frame.pack(fill="both", expand=True)
        columns = ("barcode", "product", "price", "stock")
        self.inventory_tree = self._tree(tree_frame, columns)
        for column, heading, width in [
            ("barcode", "Barcode", 150),
            ("product", "Product", 310),
            ("price", "Unit Price", 110),
            ("stock", "In Stock", 100),
        ]:
            self.inventory_tree.heading(column, text=heading)
            self.inventory_tree.column(column, width=width, anchor="w" if column in {"barcode", "product"} else "center")
        self.inventory_tree.bind("<<TreeviewSelect>>", self._inventory_selection_changed)

    def _build_history_tab(self) -> None:
        card = self._card(self.history_tab)
        card.pack(fill="both", expand=True, pady=(12, 0))
        header = ttk.Frame(card, style="Card.TFrame")
        header.pack(fill="x", pady=(0, 14))
        ttk.Label(header, text="Transaction History", style="CardTitle.TLabel").pack(
            side="left"
        )
        ttk.Button(
            header,
            text="View Receipt",
            style="Secondary.TButton",
            command=self._view_transaction,
        ).pack(side="right")
        ttk.Button(
            header,
            text="Refresh",
            style="Secondary.TButton",
            command=self._refresh_transactions,
        ).pack(side="right", padx=8)

        tree_frame = ttk.Frame(card, style="Card.TFrame")
        tree_frame.pack(fill="both", expand=True)
        columns = ("id", "type", "time", "amount", "status")
        self.history_tree = self._tree(tree_frame, columns)
        for column, heading, width in [
            ("id", "Transaction ID", 190),
            ("type", "Type", 110),
            ("time", "Date / Time", 190),
            ("amount", "Amount", 120),
            ("status", "Status", 180),
        ]:
            self.history_tree.heading(column, text=heading)
            self.history_tree.column(column, width=width, anchor="w")
        self.history_tree.bind("<Double-1>", lambda _event: self._view_transaction())

    def _build_status_bar(self) -> None:
        status = ttk.Frame(self, style="App.TFrame", padding=(26, 5, 26, 12))
        status.pack(fill="x")
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(status, textvariable=self.status_var, foreground=MUTED).pack(side="left")
        ttk.Label(
            status,
            text="F2 = complete sale",
            foreground=MUTED,
        ).pack(side="right")

    def refresh_all(self) -> None:
        self._refresh_product_choices()
        self._refresh_sale()
        self._refresh_inventory()
        self._refresh_transactions()

    def _refresh_product_choices(self) -> None:
        values = [
            f"{product.barcode}  |  {product.name}  ({product.quantity} in stock)"
            for product in self.service.products()
        ]
        self.sale_barcode.configure(values=values)

    def _refresh_sale(self) -> None:
        for item in self.sale_tree.get_children():
            self.sale_tree.delete(item)
        for line in self.draft.lines:
            self.sale_tree.insert(
                "",
                "end",
                iid=line.barcode,
                values=(
                    line.barcode,
                    line.name,
                    line.quantity,
                    format_money(line.unit_price),
                    format_money(line.line_total),
                ),
            )
        self.sale_total_var.set(format_money(self.draft.subtotal))
        self.sale_count_var.set(
            f"{self.draft.item_count} item"
            + ("" if self.draft.item_count == 1 else "s")
        )
        self._update_change_preview()

    def _refresh_inventory(self) -> None:
        for item in self.inventory_tree.get_children():
            self.inventory_tree.delete(item)
        for product in self.service.products():
            self.inventory_tree.insert(
                "",
                "end",
                iid=product.barcode,
                values=(
                    product.barcode,
                    product.name,
                    format_money(product.unit_price),
                    product.quantity,
                ),
            )

    def _refresh_transactions(self) -> None:
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        for transaction in self.service.transactions():
            if isinstance(transaction, SaleTransaction):
                transaction_type = "Sale"
                amount = transaction.total
            else:
                transaction_type = "Return"
                amount = transaction.total_refund
            self.history_tree.insert(
                "",
                "end",
                iid=transaction.transaction_id,
                values=(
                    transaction.transaction_id,
                    transaction_type,
                    transaction.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    format_money(amount),
                    transaction.status,
                ),
            )

    def _add_sale_item(self) -> None:
        raw_value = self.sale_barcode_var.get().strip()
        barcode = raw_value.split("  |  ", 1)[0].strip()
        try:
            quantity = int(self.sale_quantity.get())
            product = self.service.add_sale_item(self.draft, barcode, quantity)
        except (ValueError, tk.TclError):
            self._show_error("Quantity must be a whole number greater than zero.")
            return
        except PosError as exc:
            self._show_error(str(exc))
            return

        self._refresh_sale()
        self._refresh_product_choices()
        self.sale_barcode_var.set("")
        self.sale_quantity.set(1)
        self.sale_barcode.focus_set()
        self.status_var.set(f"Added {quantity} x {product.name}")

    def _remove_sale_item(self) -> None:
        selected = self.sale_tree.selection()
        if not selected:
            messagebox.showinfo(
                "Select an item",
                "Select a sale line to remove.",
                parent=self,
            )
            return
        try:
            self.service.remove_sale_item(self.draft, selected[0])
        except PosError as exc:
            self._show_error(str(exc))
            return
        self._refresh_sale()
        self.status_var.set("Item removed from the sale.")

    def _clear_sale(self) -> None:
        self.draft.clear()
        self.cash_var.set("")
        self.sale_quantity.set(1)
        self.sale_barcode_var.set("")
        self._refresh_sale()
        self.sale_barcode.focus_set()
        self.status_var.set("New sale started.")

    def _update_change_preview(self) -> None:
        try:
            cash = as_money(self.cash_var.get())
            difference = cash - self.draft.subtotal
            if difference < 0:
                self.change_var.set(f"Short {format_money(-difference)}")
            else:
                self.change_var.set(format_money(difference))
        except PosError:
            self.change_var.set("$0.00")

    def _complete_sale(self) -> None:
        if self.focus_get() not in {self.cash_entry, self}:
            if self.draft.lines and not self.cash_var.get().strip():
                self.cash_entry.focus_set()
                self.status_var.set("Enter the cash received to complete the sale.")
                return
        try:
            cash = as_money(self.cash_var.get())
            transaction = self.service.complete_sale(self.draft, cash)
        except PosError as exc:
            self._show_error(str(exc))
            return
        except Exception as exc:
            self._show_error(f"Could not save the sale: {exc}")
            return

        content = build_sale_receipt(transaction)
        path = save_receipt(
            self.receipt_directory,
            f"{transaction.transaction_id}.txt",
            content,
        )
        self.refresh_all()
        self.cash_var.set("")
        self.sale_quantity.set(1)
        self.sale_barcode.focus_set()
        self.status_var.set(
            f"Sale {transaction.transaction_id} complete. "
            f"Change due {format_money(transaction.change)}."
        )
        ReceiptWindow(self, "Sale Receipt", content, path)

    def _lookup_return_sale(self) -> None:
        sale_id = self.return_id_var.get().strip()
        try:
            sale = self.service.get_sale(sale_id)
        except PosError as exc:
            self._show_error(str(exc))
            return
        self.return_sale_id = sale.transaction_id
        for item in self.return_tree.get_children():
            self.return_tree.delete(item)
        for line in sale.lines:
            self.return_tree.insert(
                "",
                "end",
                iid=line.barcode,
                values=(
                    line.barcode,
                    line.name,
                    format_money(line.unit_price),
                    line.quantity,
                    line.returned_quantity,
                    line.returnable_quantity,
                ),
            )
        self.return_sale_summary.set(
            f"{sale.transaction_id}  |  "
            f"{sale.created_at:%Y-%m-%d %H:%M}  |  "
            f"Total {format_money(sale.total)}  |  {sale.status}"
        )
        self.status_var.set(f"Loaded sale {sale.transaction_id}.")

    def _return_selected_item(self) -> None:
        if not self.return_sale_id:
            messagebox.showinfo(
                "Find a sale",
                "Find the original sale before processing a return.",
                parent=self,
            )
            return
        selected = self.return_tree.selection()
        if not selected:
            messagebox.showinfo(
                "Select an item",
                "Select a returnable line from the sale.",
                parent=self,
            )
            return
        try:
            quantity = int(self.return_quantity.get())
            transaction = self.service.process_return(
                self.return_sale_id,
                {selected[0]: quantity},
            )
        except (ValueError, tk.TclError):
            self._show_error("Return quantity must be a whole number.")
            return
        except PosError as exc:
            self._show_error(str(exc))
            return
        except Exception as exc:
            self._show_error(f"Could not save the return: {exc}")
            return

        content = build_return_receipt(transaction)
        path = save_receipt(
            self.receipt_directory,
            f"{transaction.transaction_id}.txt",
            content,
        )
        self._lookup_return_sale()
        self.refresh_all()
        self.return_quantity.set(1)
        self.status_var.set(
            f"Return {transaction.transaction_id} complete. "
            f"Refund {format_money(transaction.total_refund)}."
        )
        ReceiptWindow(self, "Return Receipt", content, path)

    def _inventory_selection_changed(self, _event: tk.Event) -> None:
        selected = self.inventory_tree.selection()
        if not selected:
            return
        product = self.service.get_product(selected[0])
        self._populate_inventory_form(product)

    def _populate_inventory_form(self, product: Product) -> None:
        self.inventory_fields["barcode"].set(product.barcode)
        self.inventory_fields["name"].set(product.name)
        self.inventory_fields["price"].set(format_money(product.unit_price))
        self.inventory_fields["quantity"].set(str(product.quantity))

    def _add_product(self) -> None:
        try:
            quantity = int(self.inventory_fields["quantity"].get())
            product = self.service.add_product(
                self.inventory_fields["barcode"].get(),
                self.inventory_fields["name"].get(),
                self.inventory_fields["price"].get(),
                quantity,
            )
        except (ValueError, tk.TclError):
            self._show_error("Stock quantity must be a whole number.")
            return
        except PosError as exc:
            self._show_error(str(exc))
            return
        except Exception as exc:
            self._show_error(f"Could not save the product: {exc}")
            return
        self.refresh_all()
        self.status_var.set(f"Added {product.name}.")

    def _update_product(self) -> None:
        try:
            product = self.service.update_product(
                self.inventory_fields["barcode"].get(),
                self.inventory_fields["name"].get(),
                self.inventory_fields["price"].get(),
            )
        except PosError as exc:
            self._show_error(str(exc))
            return
        except Exception as exc:
            self._show_error(f"Could not update the product: {exc}")
            return
        self.refresh_all()
        self._populate_inventory_form(product)
        self.status_var.set(f"Updated {product.name}.")

    def _restock_product(self) -> None:
        barcode = self.inventory_fields["barcode"].get().strip()
        try:
            quantity = int(self.inventory_fields["quantity"].get())
            product = self.service.restock_product(barcode, quantity)
        except (ValueError, tk.TclError):
            self._show_error("Restock quantity must be a whole number.")
            return
        except PosError as exc:
            self._show_error(str(exc))
            return
        except Exception as exc:
            self._show_error(f"Could not update inventory: {exc}")
            return
        self.refresh_all()
        self._populate_inventory_form(product)
        self.status_var.set(
            f"Added {quantity} unit(s). {product.name} now has {product.quantity}."
        )

    def _view_transaction(self) -> None:
        selected = self.history_tree.selection()
        if not selected:
            messagebox.showinfo(
                "Select a transaction",
                "Select a transaction to view its receipt.",
                parent=self,
            )
            return
        transaction_id = selected[0]
        transaction = next(
            (
                item
                for item in self.service.transactions()
                if item.transaction_id == transaction_id
            ),
            None,
        )
        if isinstance(transaction, SaleTransaction):
            content = build_sale_receipt(transaction)
            title = "Sale Receipt"
        elif isinstance(transaction, ReturnTransaction):
            content = build_return_receipt(transaction)
            title = "Return Receipt"
        else:
            self._show_error("The transaction could not be found.")
            return
        path = save_receipt(
            self.receipt_directory,
            f"{transaction.transaction_id}.txt",
            content,
        )
        ReceiptWindow(self, title, content, path)

    def _show_error(self, message: str) -> None:
        self.status_var.set(message)
        messagebox.showerror("Point of Sale", message, parent=self)
