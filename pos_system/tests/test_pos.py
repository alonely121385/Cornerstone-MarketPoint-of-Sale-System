"""Business behavior tests for checkout, inventory, and returns."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path


PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]
if str(PROJECT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIRECTORY))

from pos.models import InsufficientStockError, PaymentError, ReturnError
from pos.repository import JsonRepository
from pos.service import PosService


WATER_BARCODE = "6900000000011"
MILK_BARCODE = "6900000000028"


class PosServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.data_path = Path(self.temporary_directory.name) / "pos_data.json"
        self.clock = lambda: datetime(2026, 11, 18, 10, 30, 0)
        self.service = PosService(JsonRepository(self.data_path), clock=self.clock)

    def _complete_sale(self, quantity: int = 2, cash: str = "10.00"):
        draft = self.service.new_sale()
        self.service.add_sale_item(draft, WATER_BARCODE, quantity)
        return self.service.complete_sale(draft, Decimal(cash))

    def test_sale_reduces_inventory_and_persists(self) -> None:
        transaction = self._complete_sale(quantity=2, cash="10.00")

        self.assertEqual(transaction.transaction_id, "SALE-20261118-0001")
        self.assertEqual(transaction.total, Decimal("4.00"))
        self.assertEqual(transaction.change, Decimal("6.00"))
        self.assertEqual(self.service.get_product(WATER_BARCODE).quantity, 58)
        self.assertEqual(len(self.service.transactions()), 1)

        reloaded = PosService(JsonRepository(self.data_path), clock=self.clock)
        self.assertEqual(reloaded.get_product(WATER_BARCODE).quantity, 58)
        self.assertEqual(reloaded.get_sale(transaction.transaction_id).total, Decimal("4.00"))

    def test_sale_rejects_insufficient_stock(self) -> None:
        draft = self.service.new_sale()
        with self.assertRaises(InsufficientStockError):
            self.service.add_sale_item(draft, WATER_BARCODE, 61)

        self.assertEqual(draft.lines, [])
        self.assertEqual(self.service.get_product(WATER_BARCODE).quantity, 60)

    def test_sale_rejects_insufficient_cash_without_changes(self) -> None:
        draft = self.service.new_sale()
        self.service.add_sale_item(draft, MILK_BARCODE, 1)

        with self.assertRaises(PaymentError):
            self.service.complete_sale(draft, Decimal("12.79"))

        self.assertEqual(self.service.get_product(MILK_BARCODE).quantity, 24)
        self.assertEqual(self.service.transactions(), [])
        self.assertEqual(len(draft.lines), 1)

    def test_partial_and_full_return_restore_inventory(self) -> None:
        sale = self._complete_sale(quantity=3, cash="10.00")

        first_return = self.service.process_return(
            sale.transaction_id,
            {WATER_BARCODE: 1},
        )
        self.assertEqual(first_return.total_refund, Decimal("2.00"))
        self.assertEqual(self.service.get_product(WATER_BARCODE).quantity, 58)
        self.assertEqual(
            self.service.get_sale(sale.transaction_id).status,
            "Partially returned",
        )

        with self.assertRaises(ReturnError):
            self.service.process_return(sale.transaction_id, {WATER_BARCODE: 3})

        second_return = self.service.process_return(
            sale.transaction_id,
            {WATER_BARCODE: 2},
        )
        self.assertEqual(second_return.total_refund, Decimal("4.00"))
        self.assertEqual(self.service.get_product(WATER_BARCODE).quantity, 60)
        self.assertEqual(
            self.service.get_sale(sale.transaction_id).status,
            "Fully returned",
        )
        self.assertEqual(
            self.service.returnable_lines(sale.transaction_id),
            [],
        )

    def test_product_management_updates_inventory(self) -> None:
        product = self.service.add_product("TEST-001", "Notebook", "7.25", 4)
        self.assertEqual(product.quantity, 4)

        updated = self.service.update_product("TEST-001", "A5 Notebook", "8.00")
        self.assertEqual(updated.name, "A5 Notebook")
        self.assertEqual(updated.unit_price, Decimal("8.00"))

        restocked = self.service.restock_product("TEST-001", 6)
        self.assertEqual(restocked.quantity, 10)


if __name__ == "__main__":
    unittest.main()
