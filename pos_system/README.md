# Cornerstone Market POS

A Python point-of-sale application implementing the two required use cases:

- **Process Sale:** add items, see the running total, accept cash, calculate
  change, reduce inventory, save a receipt, and record the transaction.
- **Handle Returns:** find the original sale, process full or partial returns,
  calculate a cash refund, restore inventory, and record the refund.

The application also includes product creation, price updates, stock
replenishment, transaction history, and persistent local data.

## Requirements

- Python 3.10 or newer
- Tkinter (included with the standard Windows Python distribution)
- No third-party packages

## Run in PyCharm

1. Open the `pos_system` folder as a project in PyCharm.
2. Select a Python 3.10+ interpreter.
3. Open `main.py`.
4. Click **Run**, or run this command from the `pos_system` directory:

   ```powershell
   python main.py
   ```

The first launch creates `data/pos_data.json` with six sample products.
Completed receipts are saved in `data/receipts/`.

## Example Workflow

1. Open **Process Sale**.
2. Scan or select barcode `6900000000011`, enter a quantity, and click
   **Add Item**.
3. Enter enough cash in **Cash received** and press **F2**.
4. Note the sale ID on the receipt.
5. Open **Handle Returns**, enter the sale ID, and click **Find Sale**.
6. Select a sale line, choose a return quantity, and click
   **Return Selected Item**.

Returns are limited to quantities that remain returnable on the original sale,
so the same item cannot be refunded twice.

## Tests

From the `pos_system` directory:

```powershell
python -m unittest discover -s tests -v
```

The tests cover successful checkout, insufficient stock, insufficient cash,
partial and full returns, over-return prevention, inventory updates, and
persistence across service restarts.

## Project Structure

```text
pos_system/
|-- main.py
|-- pos/
|   |-- models.py
|   |-- repository.py
|   |-- receipts.py
|   |-- service.py
|   `-- gui.py
|-- tests/
|   `-- test_pos.py
`-- data/                 # Created automatically
```

The design separates domain objects, persistence, use-case services, receipt
formatting, and presentation. All monetary calculations use `Decimal` to avoid
floating-point rounding errors.
