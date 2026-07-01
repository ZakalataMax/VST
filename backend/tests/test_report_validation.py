import unittest

from app.services.report import validate_custom_sql


class CustomSqlValidationTest(unittest.TestCase):
    def test_safe_select_allowed(self) -> None:
        validate_custom_sql("SELECT * FROM cust_acs_3dsmess LIMIT 10")

    def test_with_cte_allowed(self) -> None:
        validate_custom_sql(
            "WITH x AS (SELECT * FROM cust_acs_3dsmess) SELECT * FROM x"
        )

    def test_read_csv_blocked(self) -> None:
        with self.assertRaises(ValueError):
            validate_custom_sql("SELECT * FROM read_csv('C:/secret.csv')")

    def test_read_parquet_blocked(self) -> None:
        with self.assertRaises(ValueError):
            validate_custom_sql("SELECT * FROM read_parquet('x.parquet')")

    def test_glob_blocked(self) -> None:
        with self.assertRaises(ValueError):
            validate_custom_sql("SELECT * FROM glob('C:/*')")

    def test_attach_blocked(self) -> None:
        with self.assertRaises(ValueError):
            validate_custom_sql("ATTACH 'other.db' AS o")

    def test_copy_blocked(self) -> None:
        with self.assertRaises(ValueError):
            validate_custom_sql("COPY cust_acs_3dsmess TO 'out.csv'")

    def test_multiple_statements_blocked(self) -> None:
        with self.assertRaises(ValueError):
            validate_custom_sql("SELECT 1; SELECT 2")

    def test_function_name_in_string_literal_allowed(self) -> None:
        validate_custom_sql(
            "SELECT * FROM cust_acs_3dsmess WHERE merchantname = 'read_csv('"
        )


if __name__ == "__main__":
    unittest.main()
