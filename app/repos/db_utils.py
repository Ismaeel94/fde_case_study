def sql_string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
