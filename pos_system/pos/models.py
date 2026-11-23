"""Domain models for products, sales, and returns."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


MONEY_PLACES = Decimal("0.01")


class PosError(Exception):
    """Base exception for expected business errors."""


class ValidationError(PosError):
    """Raised when user input is invalid."""


class NotFoundError(PosError):
    """Raised when a product or transaction cannot be found."""


class InsufficientStockError(PosError):
    """Raised when a sale requests more stock than is available."""


class PaymentError(PosError):
    """Raised when a cash payment is invalid."""


class ReturnError(PosError):
    """Raised when a return cannot be completed."""


def as_money(value: Decimal | str | int | float) -> Decimal:
    """Convert a value to a two-decimal monetary amount."""

    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("Enter a valid monetary amount.") from exc
    if not amount.is_finite():
        raise ValidationError("Enter a valid monetary amount.")
    return amount.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def format_money(value: Decimal | str | int | float) -> str:
    """Format a monetary value for display and receipts."""

    return f"${as_money(value):,.2f}"


@dataclass(frozen=True)
class Product:
    """A sellable product and its current inventory quantity."""

    barcode: str
    name: str
    unit_price: Decimal
    quantity: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Product":
        return cls(
            barcode=str(data["barcode"]),
            name=str(data["name"]),
            unit_price=as_money(data["unit_price"]),
            quantity=int(data["quantity"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "barcode": self.barcode,
            "name": self.name,
            "unit_price": str(self.unit_price),
            "quantity": self.quantity,
        }


@dataclass
class SaleLine:
    """An item currently held in an unfinished sale."""

    barcode: str
    name: str
    unit_price: Decimal
    quantity: int

    @property
    def line_total(self) -> Decimal:
        return as_money(self.unit_price * self.quantity)


@dataclass
class SaleDraft:
    """A cashier's working cart before payment is completed."""

    lines: list[SaleLine] = field(default_factory=list)

    @property
    def subtotal(self) -> Decimal:
        return as_money(sum((line.line_total for line in self.lines), Decimal("0")))

    @property
    def item_count(self) -> int:
        return sum(line.quantity for line in self.lines)

    def quantity_for(self, barcode: str) -> int:
        return next(
            (line.quantity for line in self.lines if line.barcode == barcode),
            0,
        )

    def add(self, product: Product, quantity: int) -> None:
        if quantity <= 0:
            raise ValidationError("Quantity must be greater than zero.")
        existing = next(
            (line for line in self.lines if line.barcode == product.barcode),
            None,
        )
        if existing:
            existing.quantity += quantity
        else:
            self.lines.append(
                SaleLine(
                    barcode=product.barcode,
                    name=product.name,
                    unit_price=product.unit_price,
                    quantity=quantity,
                )
            )

    def remove(self, barcode: str) -> None:
        before = len(self.lines)
        self.lines = [line for line in self.lines if line.barcode != barcode]
        if len(self.lines) == before:
            raise NotFoundError("The selected item is not in the sale.")

    def clear(self) -> None:
        self.lines.clear()


@dataclass
class TransactionLine:
    """A completed sale line that can be returned later."""

    barcode: str
    name: str
    unit_price: Decimal
    quantity: int
    returned_quantity: int = 0

    @property
    def line_total(self) -> Decimal:
        return as_money(self.unit_price * self.quantity)

    @property
    def returnable_quantity(self) -> int:
        return max(0, self.quantity - self.returned_quantity)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TransactionLine":
        return cls(
            barcode=str(data["barcode"]),
            name=str(data["name"]),
            unit_price=as_money(data["unit_price"]),
            quantity=int(data["quantity"]),
            returned_quantity=int(data.get("returned_quantity", 0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "barcode": self.barcode,
            "name": self.name,
            "unit_price": str(self.unit_price),
            "quantity": self.quantity,
            "returned_quantity": self.returned_quantity,
        }


@dataclass
class SaleTransaction:
    """A completed cash sale."""

    transaction_id: str
    created_at: datetime
    lines: list[TransactionLine]
    total: Decimal
    cash_received: Decimal

    @property
    def change(self) -> Decimal:
        return as_money(self.cash_received - self.total)

    @property
    def status(self) -> str:
        returned = sum(line.returned_quantity for line in self.lines)
        sold = sum(line.quantity for line in self.lines)
        if returned == 0:
            return "Completed"
        if returned >= sold:
            return "Fully returned"
        return "Partially returned"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SaleTransaction":
        return cls(
            transaction_id=str(data["transaction_id"]),
            created_at=datetime.fromisoformat(str(data["created_at"])),
            lines=[TransactionLine.from_dict(line) for line in data["lines"]],
            total=as_money(data["total"]),
            cash_received=as_money(data["cash_received"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "sale",
            "transaction_id": self.transaction_id,
            "created_at": self.created_at.isoformat(timespec="seconds"),
            "lines": [line.to_dict() for line in self.lines],
            "total": str(self.total),
            "cash_received": str(self.cash_received),
        }


@dataclass
class ReturnLine:
    """A quantity returned from one original sale line."""

    barcode: str
    name: str
    unit_price: Decimal
    quantity: int

    @property
    def line_total(self) -> Decimal:
        return as_money(self.unit_price * self.quantity)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReturnLine":
        return cls(
            barcode=str(data["barcode"]),
            name=str(data["name"]),
            unit_price=as_money(data["unit_price"]),
            quantity=int(data["quantity"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "barcode": self.barcode,
            "name": self.name,
            "unit_price": str(self.unit_price),
            "quantity": self.quantity,
        }


@dataclass
class ReturnTransaction:
    """A cash refund linked to an earlier sale."""

    transaction_id: str
    original_transaction_id: str
    created_at: datetime
    lines: list[ReturnLine]
    total_refund: Decimal

    @property
    def status(self) -> str:
        return "Refunded"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReturnTransaction":
        return cls(
            transaction_id=str(data["transaction_id"]),
            original_transaction_id=str(data["original_transaction_id"]),
            created_at=datetime.fromisoformat(str(data["created_at"])),
            lines=[ReturnLine.from_dict(line) for line in data["lines"]],
            total_refund=as_money(data["total_refund"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "return",
            "transaction_id": self.transaction_id,
            "original_transaction_id": self.original_transaction_id,
            "created_at": self.created_at.isoformat(timespec="seconds"),
            "lines": [line.to_dict() for line in self.lines],
            "total_refund": str(self.total_refund),
        }


Transaction = SaleTransaction | ReturnTransaction
