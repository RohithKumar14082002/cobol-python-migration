"""Python translation of the loan EMI calculation in the COBOL sample."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


CENT = Decimal("0.01")


@dataclass(frozen=True)
class Installment:
    month: int
    payment: Decimal
    interest: Decimal
    principal: Decimal
    balance: Decimal


def _as_decimal(value: Decimal | str | int, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{field} must be a valid number") from error
    if not result.is_finite():
        raise ValueError(f"{field} must be finite")
    return result


def calculate_emi(
    principal: Decimal | str | int,
    annual_rate_percent: Decimal | str | int,
    months: int,
) -> tuple[Decimal, list[Installment]]:
    """Return the rounded monthly payment and amortization schedule."""
    principal = _as_decimal(principal, "principal")
    annual_rate_percent = _as_decimal(annual_rate_percent, "annual rate")

    if principal <= 0:
        raise ValueError("principal must be greater than zero")
    if annual_rate_percent < 0:
        raise ValueError("annual rate cannot be negative")
    if isinstance(months, bool) or not isinstance(months, int) or months <= 0:
        raise ValueError("months must be a positive integer")

    monthly_rate = annual_rate_percent / Decimal("1200")
    if monthly_rate == 0:
        payment = (principal / months).quantize(CENT, rounding=ROUND_HALF_UP)
    else:
        growth = (Decimal("1") + monthly_rate) ** months
        payment = (principal * monthly_rate * growth / (growth - 1)).quantize(
            CENT, rounding=ROUND_HALF_UP
        )

    balance = principal.quantize(CENT, rounding=ROUND_HALF_UP)
    schedule: list[Installment] = []
    for month in range(1, months + 1):
        interest = (balance * monthly_rate).quantize(CENT, rounding=ROUND_HALF_UP)
        installment_payment = payment if month < months else balance + interest
        principal_paid = installment_payment - interest
        balance = max(Decimal("0.00"), balance - principal_paid)
        schedule.append(
            Installment(
                month=month,
                payment=installment_payment,
                interest=interest,
                principal=principal_paid,
                balance=balance,
            )
        )

    return payment, schedule


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate a loan EMI schedule.")
    parser.add_argument("principal", type=Decimal, help="loan amount, for example 10000")
    parser.add_argument("annual_rate", type=Decimal, help="annual rate in percent, for example 12")
    parser.add_argument("months", type=int, help="repayment period in months")
    arguments = parser.parse_args()

    try:
        payment, schedule = calculate_emi(
            arguments.principal, arguments.annual_rate, arguments.months
        )
    except ValueError as error:
        parser.error(str(error))

    print(f"Monthly payment: {payment:.2f}")
    print("Month  Payment  Interest  Principal  Balance")
    for item in schedule:
        print(
            f"{item.month:>5}  {item.payment:>7.2f}  {item.interest:>8.2f}"
            f"  {item.principal:>9.2f}  {item.balance:>7.2f}"
        )


if __name__ == "__main__":
    main()