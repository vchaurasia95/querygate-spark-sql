import sqlglot
from sqlglot.errors import ParseError

def validate_sql_syntax(sql: str) -> dict:
    """
    Validate the syntax of a SQL query using SQLGlot.

    Parameters:
        sql (str): The SQL query string to validate.

    Returns:
        dict: A dictionary with the following structure:
              {
                  "valid": bool,          # True if syntax is valid, False if error found
                  "message": str          # Validation result or error message
              }
    """
    try:
        print("Input to tool -->" + sql)
        dialect: str = "spark"
        expr = sqlglot.parse_one(sql, read=dialect)

        return {
            "valid": True,
            "message": "SQL syntax is valid."
        }

    except ParseError as e:
        return {
            "valid": False,
            "message": f"Syntax error: {str(e)}"
        }
    