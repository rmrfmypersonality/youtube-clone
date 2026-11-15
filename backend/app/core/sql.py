def escape_like(value: str) -> str:
    """Экранирует % и _ в пользовательском вводе для LIKE/ILIKE (с escape='\\')."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")