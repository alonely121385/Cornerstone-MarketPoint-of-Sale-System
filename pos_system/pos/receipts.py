"""Plain-text receipt generation."""

from __future__ import annotations

from pathlib import Path

from .models import ReturnTransaction, SaleTransaction, format_money


RECEIPT_WIDTH = 48


def _center(text: str, width: int = RECEIPT_WIDTH) -> str:
    return text.center(width)


def _line(character: str = "-") -> str:
    return character * RECEIPT_WIDTH


def _item_row(name: str, quantity: int, unit_price, line_total) -> list[str]:
    first_line = f"{name[:28]:28} {quantity:>3} x"
    second_line = f"  {format_money(unit_price):>14} {format_money(line_total):>16}"
    return [first_line, second_line]


def build_sale_receipt(transaction: SaleTransaction) -> str:
    """Create a cashier-readable receipt for a completed sale."""

    rows = [
        _line("="),
        _center("CORNERSTONE MARKET"),
        _center("Point-of-Sale Receipt"),
        _line("="),
        f"Sale:    {transaction.transaction_id}",
        f"Date:    {transaction.created_at:%Y-%m-%d %H:%M:%S}",
        _line(),
    ]
    for line in transaction.lines:
        rows.extend(
            _item_row(
                line.name,
                line.quantity,
                line.unit_price,
                line.line_total,
            )
        )
    rows.extend(
        [
            _line(),
            f"{'TOTAL':<24}{format_money(transaction.total):>24}",
            f"{'CASH':<24}{format_money(transaction.cash_received):>24}",
            f"{'CHANGE':<24}{format_money(transaction.change):>24}",
            _line("="),
            _center("Thank you for shopping with us."),
            _center("Keep this receipt for returns."),
            _line("="),
        ]
    )
    return "\n".join(rows) + "\n"


def build_return_receipt(transaction: ReturnTransaction) -> str:
    """Create a receipt for a completed cash refund."""

    rows = [
        _line("="),
        _center("CORNERSTONE MARKET"),
        _center("Return Receipt"),
        _line("="),
        f"Return:  {transaction.transaction_id}",
        f"Sale:    {transaction.original_transaction_id}",
        f"Date:    {transaction.created_at:%Y-%m-%d %H:%M:%S}",
        _line(),
    ]
    for line in transaction.lines:
        rows.extend(
            _item_row(
                line.name,
                line.quantity,
                line.unit_price,
                line.line_total,
            )
        )
    rows.extend(
        [
            _line(),
            f"{'REFUND':<24}{format_money(transaction.total_refund):>24}",
            _line("="),
            _center("Refund paid in cash."),
            _line("="),
        ]
    )
    return "\n".join(rows) + "\n"


def save_receipt(directory: Path, filename: str, content: str) -> Path:
    """Save receipt text beside the application's data file."""

    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(content, encoding="utf-8")
    return path
