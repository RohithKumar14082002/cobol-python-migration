import unittest
from decimal import Decimal

from emi_calculator import calculate_emi


class CalculateEmiTests(unittest.TestCase):
    def test_standard_loan_and_final_balance(self) -> None:
        payment, schedule = calculate_emi("10000", "12", 12)

        self.assertEqual(payment, Decimal("888.49"))
        self.assertEqual(len(schedule), 12)
        self.assertEqual(schedule[0].interest, Decimal("100.00"))
        self.assertEqual(schedule[0].principal, Decimal("788.49"))
        self.assertEqual(schedule[-1].balance, Decimal("0.00"))

    def test_zero_interest(self) -> None:
        payment, schedule = calculate_emi("1200", "0", 12)

        self.assertEqual(payment, Decimal("100.00"))
        self.assertEqual(sum((row.interest for row in schedule), Decimal("0")), Decimal("0"))
        self.assertEqual(schedule[-1].balance, Decimal("0.00"))

    def test_rejects_invalid_inputs(self) -> None:
        for values in (("0", "12", 12), ("100", "-1", 12), ("100", "12", 0)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                calculate_emi(*values)


if __name__ == "__main__":
    unittest.main()