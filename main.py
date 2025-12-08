import csv
import os
import requests

CSV_FILE = "transactions.csv"
BASE_CURRENCY = "GBP"  # the currency we convert everything into for balances

# Ensure CSV exists with correct header
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Date", "Description", "Category", "OriginalAmount", "OriginalCurrency", "AmountGBP"])


# ---- Currency helper / Frankfurter integration ----
def get_exchange_rate(from_currency: str, to_currency: str = BASE_CURRENCY) -> float | None:
    """
    Returns conversion rate from `from_currency` to `to_currency` using Frankfurter.
    Returns None on failure.
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()
    if from_currency == to_currency:
        return 1.0

    try:
        url = f"https://api.frankfurter.app/latest?from={from_currency}&to={to_currency}"
        resp = requests.get(url, timeout=6)
        resp.raise_for_status()
        data = resp.json()
        rate = data["rates"].get(to_currency)
        if rate is None:
            return None
        return float(rate)
    except Exception:
        # network error, timeout, or unexpected response
        return None


def choose_currency_menu() -> str:
    """
    Presents a small menu of common currencies plus 'Other'.
    Returns the chosen ISO currency code (uppercase).
    """
    options = [
        ("GBP", "British Pound"),
        ("EUR", "Euro"),
        ("USD", "US Dollar"),
        ("JPY", "Japanese Yen"),
        ("AUD", "Australian Dollar"),
        ("CAD", "Canadian Dollar"),
        ("INR", "Indian Rupee"),
        ("Other", "Enter a different currency code")
    ]

    print("\nChoose currency:")
    for i, (code, name) in enumerate(options, start=1):
        print(f"{i}. {code} ({name})")

    while True:
        choice = input("Enter number (1-8): ").strip()
        if not choice.isdigit():
            print("Please enter a number.")
            continue
        idx = int(choice)
        if 1 <= idx <= len(options):
            code = options[idx - 1][0]
            if code == "Other":
                # ask user to type a code
                custom = input("Enter ISO currency code (e.g. USD, EUR, JPY): ").strip().upper()
                return custom or BASE_CURRENCY
            return code
        print("Invalid choice, try again.")


# ---- CRUD functions ----
def add_transaction():
    date = input("Enter the date (YYYY-MM-DD): ").strip()
    description = input("Enter the description: ").strip()
    category = input("Enter the category: ").strip()

    original_currency = choose_currency_menu()

    # Get amount in original currency
    while True:
        try:
            amt_text = input(f"Enter the amount in {original_currency}: ").strip()
            original_amount = float(amt_text)
            break
        except ValueError:
            print("Invalid number. Try again (e.g. 50 or -25.5).")

    # Income or Expense -> enforce sign
    while True:
        t_type = input("Is this an Income or Expense? (I/E): ").strip().upper()
        if t_type in ("I", "E"):
            if t_type == "E":
                original_amount = -abs(original_amount)
            else:
                original_amount = abs(original_amount)
            break
        print("Invalid choice. Enter 'I' for Income or 'E' for Expense.")

    # Get exchange rate and compute GBP amount
    rate = get_exchange_rate(original_currency, BASE_CURRENCY)
    if rate is None:
        print("Warning: could not fetch exchange rate; storing GBP as 0.0 (you can update later).")
        amount_gbp = 0.0
    else:
        amount_gbp = original_amount * rate

    # Write to CSV
    with open(CSV_FILE, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([date, description, category, original_amount, original_currency, f"{amount_gbp:.2f}"])

    print(f"Transaction added: {original_amount} {original_currency} -> £{amount_gbp:.2f}")


def view_transactions():
    if not os.path.exists(CSV_FILE):
        print("No transactions yet.")
        return

    with open(CSV_FILE, "r", newline="") as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader, None)  # skip header

        has_entry = False
        print("\n--- All Transactions ---")
        for i, row in enumerate(reader, start=1):
            if len(row) == 6:
                date, description, category, original_amount, original_currency, amount_gbp = row
                try:
                    # present amounts nicely
                    oa = float(original_amount)
                    ag = float(amount_gbp)
                    tran_type = "Income" if oa >= 0 else "Expense"
                    print(f"{i}. Date: {date}, Desc: {description}, Cat: {category}, "
                          f"{original_amount} {original_currency} (GBP: £{ag:.2f}) [{tran_type}]")
                except ValueError:
                    print(f"{i}. Date: {date}, Desc: {description}, Cat: {category}, RAW AMOUNTS: {original_amount}, {amount_gbp}")
                has_entry = True
            else:
                print(f"{i}. Malformed row: {row}")

        if not has_entry:
            print("No transactions recorded yet.")
        print("-------------------------\n")


def delete_transaction():
    if not os.path.exists(CSV_FILE):
        print("No transactions file found.")
        return

    with open(CSV_FILE, "r", newline="") as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader, None)
        rows = [row for row in reader if row]

    if not rows:
        print("No transactions to delete.")
        return

    print("\n--- Transactions ---")
    for i, row in enumerate(rows, start=1):
        if len(row) == 6:
            date, description, category, original_amount, currency, amount_gbp = row
            try:
                oa = float(original_amount)
                tran_type = "Income" if oa >= 0 else "Expense"
                print(f"{i}. Date: {date}, Desc: {description}, Cat: {category}, {original_amount} {currency} [{tran_type}]")
            except ValueError:
                print(f"{i}. {row}")
        else:
            print(f"{i}. {row}")
    print("--------------------\n")

    choice = input("Enter the number of the transaction to delete (or 'c' to cancel): ").strip()
    if choice.lower() == 'c':
        print("Delete cancelled.")
        return
    if not choice.isdigit():
        print("Invalid choice.")
        return

    index = int(choice) - 1
    if index < 0 or index >= len(rows):
        print("No transaction found with that number. No transaction deleted.")
        return

    to_remove = rows[index]
    preview = ", ".join(to_remove) if isinstance(to_remove, list) else str(to_remove)
    confirm = input(f"Are you sure you want to delete transaction #{index + 1}: {preview}? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Delete cancelled.")
        return

    del rows[index]
    with open(CSV_FILE, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        if header:
            writer.writerow(header)
        for row in rows:
            writer.writerow(row)

    print("Transaction deleted successfully.")


def update_transaction():
    # recalculates GBP if currency/amount changed
    if not os.path.exists(CSV_FILE):
        print("No transactions file found.")
        return

    with open(CSV_FILE, "r", newline="") as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader, None)
        rows = [row for row in reader if row]

    if not rows:
        print("No transactions to edit.")
        return

    print("\n--- Transactions ---")
    for i, row in enumerate(rows, start=1):
        if len(row) == 6:
            date, description, category, original_amount, currency, amount_gbp = row
            try:
                oa = float(original_amount)
                tran_type = "Income" if oa >= 0 else "Expense"
                print(f"{i}. Date: {date}, Desc: {description}, Cat: {category}, {abs(oa)} {currency} [{tran_type}]")
            except ValueError:
                print(f"{i}. {row}")
        else:
            print(f"{i}. {row}")
    print("--------------------\n")

    choice = input("Enter the number of the transaction to edit (or 'c' to cancel): ").strip()
    if choice.lower() == 'c':
        print("Edit cancelled.")
        return
    if not choice.isdigit():
        print("Invalid choice.")
        return

    index = int(choice) - 1
    if index < 0 or index >= len(rows):
        print("Number out of range.")
        return

    old_row = rows[index]
    date = input(f"Enter new date (YYYY-MM-DD) [{old_row[0]}]: ").strip() or old_row[0]
    description = input(f"Enter new description [{old_row[1]}]: ").strip() or old_row[1]
    category = input(f"Enter new category [{old_row[2]}]: ").strip() or old_row[2]

    # currency menu
    print("Currency selection (press Enter to keep current):")
    print(f"Current currency: {old_row[4]}")
    new_currency = choose_currency_menu()
    if new_currency == "":
        new_currency = old_row[4]

    # amount input
    while True:
        amount_input = input(f"Enter new amount [{old_row[3]}]: ").strip()
        if amount_input == "":
            new_original_amount = float(old_row[3])
            break
        try:
            new_original_amount = float(amount_input)
            break
        except ValueError:
            print("Invalid amount. Try again.")

    # Income/Expense sign
    while True:
        t_type = input("Is this an Income or Expense? (I/E) [press Enter to keep current]: ").strip().upper()
        if t_type in ("I", "E", ""):
            if t_type == "I":
                new_original_amount = abs(new_original_amount)
            elif t_type == "E":
                new_original_amount = -abs(new_original_amount)
            break
        print("Invalid choice. Enter I, E, or press Enter.")

    # Recalculate GBP
    rate = get_exchange_rate(new_currency, BASE_CURRENCY)
    if rate is None:
        print("Warning: could not fetch exchange rate; storing GBP as 0.0 (you can update later).")
        new_amount_gbp = 0.0
    else:
        new_amount_gbp = new_original_amount * rate

    # Update row
    rows[index] = [date, description, category, f"{new_original_amount}", new_currency, f"{new_amount_gbp:.2f}"]

    # Write back CSV
    with open(CSV_FILE, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        if header:
            writer.writerow(header)
        for row in rows:
            writer.writerow(row)

    print("Transaction updated successfully.")


def show_balance():
    if not os.path.exists(CSV_FILE):
        print("No transactions file found.")
        return

    with open(CSV_FILE, "r", newline="") as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader, None)
        rows = [row for row in reader if row]

    if not rows:
        print("No transactions recorded yet.")
        return

    total_expenses = 0.0
    total_income = 0.0

    for row in rows:
        if len(row) == 6:
            try:
                amount = float(row[3])
                if amount >= 0:
                    total_income += amount
                else:
                    total_expenses += abs(amount)
            except ValueError:
                print(f"Skipping invalid amount: {row[3]}")

    net_balance = total_income - total_expenses

    print("\n=== Balance Summary ===")
    print(f"Total Income: £{total_income:.2f}")
    print(f"Total Expenses: £{total_expenses:.2f}")
    print(f"Net Balance: £{net_balance:.2f}")
    print("======================\n")


def main():
    while True:
        print(" ===Finance Tracker=== ")
        print("1. Add transaction")
        print("2. View transactions")
        print("3. Delete transaction")
        print("4. Edit transaction")
        print("5. Show balance")
        print("6. Exit")

        choice = input("Enter your choice: ")

        if choice == "1":
            add_transaction()

        elif choice == "2":
            view_transactions()

        elif choice == "3":
            delete_transaction()

        elif choice == "4":
            update_transaction()

        elif choice == "5":
            show_balance()

        elif choice == "6":
            print("Finance Tracker has stopped")
            break
        else:
            print("Invalid Choice, try again!\n")


if __name__ == "__main__":
    main()
