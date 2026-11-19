import tempfile
import unittest
from pathlib import Path

from focus4_report import aggregate_records, read_mainfile_csv, render_report


class Focus4ReportTests(unittest.TestCase):
    def test_sample_mainfile_aggregates_and_renders(self) -> None:
        sample_path = Path(__file__).with_name("SAMPLE-MAINFILE.csv")

        rows = aggregate_records(read_mainfile_csv(sample_path))
        report = render_report(rows)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].product_type, "LAPTOP")
        self.assertEqual(str(rows[0].amount), "20.25")
        self.assertEqual(str(rows[0].product_count), "2.00")
        self.assertIn("<td>ELECTRONICS</td><td>LAPTOP</td>", report)
        self.assertIn('<td align="right">20.25</td><td align="right">2.00</td>', report)
        self.assertIn("<html", report)

    def test_csv_rejects_amount_with_more_than_two_decimals(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "mainfile.csv"
            csv_path.write_text(
                "MAIN-KEY,AMOUNT,PROD-TYPE\nK000000001,1.234,LAPTOP\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "at most two decimal places"):
                read_mainfile_csv(csv_path)


if __name__ == "__main__":
    unittest.main()