"""Business services and use-case orchestration for the POS."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from typing import Callable

from .models import (
    InsufficientStockError,
    NotFoundError,
    PaymentError,
    PosError,
    Product,
    ReturnError,
    ReturnLine,
    ReturnTransaction,
    SaleDraft,
    SaleTransaction,
    TransactionLine,
    ValidationError,
    as_money,
)
from .repository import JsonRepository


class PosService:
    """Coordinate inventory, checkout, returns, and persistence."""

    def __init__(
        self,
        repository: JsonRepository,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self._clock = clock or datetime.now
        state = repository.load()
        self._products = {
            item["barcode"]: Product.from_dict(item) for item in state["products"]
        }
        self._transactions = [
            self._transaction_from_dict(item) for item in state["transactions"]
        ]

    @staticmethod
    def _transaction_from_dict(data: dict) -> SaleTransaction | ReturnTransaction:
        transaction_type = data.get("type")
        if transaction_type == "sale":
            return SaleTransaction.from_dict(data)
        if transaction_type == "return":
            return ReturnTransaction.from_dict(data)
        raise ValidationError("Application data contains an unknown transaction type.")

    def products(self) -> list[Product]:
        return sorted(self._products.values(), key=lambda product: product.name.lower())

    def get_product(self, barcode: str) -> Product:
        normalized = barcode.strip()
        product = self._products.get(normalized)
        if product is None:
            raise NotFoundError(f"No product was found for barcode {normalized!r}.")
        return product

    def new_sale(self) -> SaleDraft:
        return SaleDraft()

    def add_sale_item(
        self,
        draft: SaleDraft,
        barcode: str,
        quantity: int,
    ) -> Product:
        if quantity <= 0:
            raise ValidationError("Quantity must be greater than zero.")
        product = self.get_product(barcode)
        requested_quantity = draft.quantity_for(product.barcode) + quantity
        if requested_quantity > product.quantity:
            raise InsufficientStockError(
                f"Only {product.quantity} unit(s) of {product.name} are available."
            )
        draft.add(product, quantity)
        return product

    def remove_sale_item(self, draft: SaleDraft, barcode: str) -> None:
        draft.remove(barcode)

    def complete_sale(self, draft: SaleDraft, cash_received: Decimal) -> SaleTransaction:
        if not draft.lines:
            raise ValidationError("Add at least one item before completing the sale.")

        payment = as_money(cash_received)
        total = draft.subtotal
        if payment < total:
            raise PaymentError(
                f"Cash received is short by {as_money(total - payment)}."
            )

        for line in draft.lines:
            product = self._products.get(line.barcode)
            if product is None:
                raise NotFoundError(f"Product {line.barcode} no longer exists.")
            if line.quantity > product.quantity:
                raise InsufficientStockError(
                    f"Stock for {product.name} changed. "
                    f"Only {product.quantity} unit(s) remain."
                )

        products_before = deepcopy(self._products)
        transactions_before = deepcopy(self._transactions)
        try:
            for line in draft.lines:
                product = self._products[line.barcode]
                self._products[line.barcode] = Product(
                    barcode=product.barcode,
                    name=product.name,
                    unit_price=product.unit_price,
                    quantity=product.quantity - line.quantity,
                )

            now = self._clock()
            transaction = SaleTransaction(
                transaction_id=self._next_id("SALE", now),
                created_at=now,
                lines=[
                    TransactionLine(
                        barcode=line.barcode,
                        name=line.name,
                        unit_price=line.unit_price,
                        quantity=line.quantity,
                    )
                    for line in draft.lines
                ],
                total=total,
                cash_received=payment,
            )
            self._transactions.append(transaction)
            self._save()
            draft.clear()
            return transaction
        except Exception:
            self._products = products_before
            self._transactions = transactions_before
            raise

    def get_sale(self, transaction_id: str) -> SaleTransaction:
        normalized = transaction_id.strip().upper()
        for transaction in self._transactions:
            if (
                isinstance(transaction, SaleTransaction)
                and transaction.transaction_id.upper() == normalized
            ):
                return transaction
        raise NotFoundError(f"Sale {transaction_id!r} was not found.")

    def returnable_lines(self, transaction_id: str) -> list[TransactionLine]:
        sale = self.get_sale(transaction_id)
        return [line for line in sale.lines if line.returnable_quantity > 0]

    def process_return(
        self,
        transaction_id: str,
        quantities: dict[str, int],
    ) -> ReturnTransaction:
        sale = self.get_sale(transaction_id)
        selections = {barcode: quantity for barcode, quantity in quantities.items()}
        selected_total = sum(selections.values())
        if selected_total <= 0:
            raise ReturnError("Select at least one item to return.")
        if any(quantity <= 0 for quantity in selections.values()):
            raise ValidationError("Return quantity must be greater than zero.")

        sale_lines = {line.barcode: line for line in sale.lines}
        for barcode, quantity in selections.items():
            line = sale_lines.get(barcode)
            if line is None:
                raise ReturnError(f"Barcode {barcode} is not part of this sale.")
            if quantity > line.returnable_quantity:
                raise ReturnError(
                    f"Only {line.returnable_quantity} unit(s) of {line.name} "
                    "can still be returned."
                )
            if barcode not in self._products:
                raise ReturnError(f"Product {line.name} is not in the inventory.")

        products_before = deepcopy(self._products)
        transactions_before = deepcopy(self._transactions)
        try:
            return_lines: list[ReturnLine] = []
            for barcode, quantity in selections.items():
                line = sale_lines[barcode]
                product = self._products[barcode]
                self._products[barcode] = Product(
                    barcode=product.barcode,
                    name=product.name,
                    unit_price=product.unit_price,
                    quantity=product.quantity + quantity,
                )
                line.returned_quantity += quantity
                return_lines.append(
                    ReturnLine(
                        barcode=line.barcode,
                        name=line.name,
                        unit_price=line.unit_price,
                        quantity=quantity,
                    )
                )

            now = self._clock()
            refund = as_money(
                sum((line.line_total for line in return_lines), Decimal("0"))
            )
            transaction = ReturnTransaction(
                transaction_id=self._next_id("RET", now),
                original_transaction_id=sale.transaction_id,
                created_at=now,
                lines=return_lines,
                total_refund=refund,
            )
            self._transactions.append(transaction)
            self._save()
            return transaction
        except Exception:
            self._products = products_before
            self._transactions = transactions_before
            raise

    def add_product(
        self,
        barcode: str,
        name: str,
        unit_price: Decimal | str | int | float,
        quantity: int,
    ) -> Product:
        normalized_barcode = barcode.strip()
        normalized_name = name.strip()
        if not normalized_barcode:
            raise ValidationError("Barcode is required.")
        if not normalized_name:
            raise ValidationError("Product name is required.")
        if normalized_barcode in self._products:
            raise ValidationError("A product with this barcode already exists.")
        if quantity < 0:
            raise ValidationError("Stock quantity cannot be negative.")
        price = as_money(unit_price)
        if price < 0:
            raise ValidationError("Unit price cannot be negative.")

        product = Product(normalized_barcode, normalized_name, price, quantity)
        products_before = deepcopy(self._products)
        try:
            self._products[product.barcode] = product
            self._save()
            return product
        except Exception:
            self._products = products_before
            raise

    def update_product(
        self,
        barcode: str,
        name: str,
        unit_price: Decimal | str | int | float,
    ) -> Product:
        current = self.get_product(barcode)
        normalized_name = name.strip()
        if not normalized_name:
            raise ValidationError("Product name is required.")
        price = as_money(unit_price)
        if price < 0:
            raise ValidationError("Unit price cannot be negative.")

        updated = Product(
            barcode=current.barcode,
            name=normalized_name,
            unit_price=price,
            quantity=current.quantity,
        )
        products_before = deepcopy(self._products)
        try:
            self._products[current.barcode] = updated
            self._save()
            return updated
        except Exception:
            self._products = products_before
            raise

    def restock_product(self, barcode: str, quantity: int) -> Product:
        if quantity <= 0:
            raise ValidationError("Restock quantity must be greater than zero.")
        current = self.get_product(barcode)
        updated = Product(
            barcode=current.barcode,
            name=current.name,
            unit_price=current.unit_price,
            quantity=current.quantity + quantity,
        )
        products_before = deepcopy(self._products)
        try:
            self._products[current.barcode] = updated
            self._save()
            return updated
        except Exception:
            self._products = products_before
            raise

    def transactions(self, limit: int | None = None) -> list[SaleTransaction | ReturnTransaction]:
        ordered = sorted(
            self._transactions,
            key=lambda transaction: transaction.created_at,
            reverse=True,
        )
        return ordered[:limit] if limit is not None else ordered

    def _next_id(self, prefix: str, now: datetime) -> str:
        date_text = now.strftime("%Y%m%d")
        full_prefix = f"{prefix}-{date_text}-"
        used_numbers = []
        for transaction in self._transactions:
            transaction_id = transaction.transaction_id
            if transaction_id.startswith(full_prefix):
                suffix = transaction_id.removeprefix(full_prefix)
                if suffix.isdigit():
                    used_numbers.append(int(suffix))
        next_number = max(used_numbers, default=0) + 1
        return f"{full_prefix}{next_number:04d}"

    def _save(self) -> None:
        self.repository.save(
            {
                "schema_version": 1,
                "products": [product.to_dict() for product in self._products.values()],
                "transactions": [
                    transaction.to_dict() for transaction in self._transactions
                ],
            }
        )

    @staticmethod
    def error_message(error: PosError) -> str:
        return str(error)
