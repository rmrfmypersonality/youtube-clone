from app.main import app


def _string_schemas(prop: dict):
    if "anyOf" in prop:
        for p in prop["anyOf"]:
            yield from _string_schemas(p)
    elif prop.get("type") == "string":
        yield prop


def _bounded(schema: dict) -> bool:
    # email проверяется отдельным валидатором (не длиннее 254)
    return any(k in schema for k in ("maxLength", "pattern", "enum", "const")) or schema.get("format") == "email"


def test_every_string_input_has_a_limit():
    """Новое текстовое поле без max_length или pattern ломает этот тест."""
    spec = app.openapi()
    schemas = spec["components"]["schemas"]
    problems: list[str] = []

    for path, methods in spec["paths"].items():
        for method, op in methods.items():
            if not isinstance(op, dict):
                continue
            body = op.get("requestBody", {}).get("content", {}).get("application/json")
            if body:
                ref = body["schema"].get("$ref")
                if ref is None:
                    problems.append(f"{method.upper()} {path}: тело без именованной схемы")
                else:
                    name = ref.rsplit("/", 1)[-1]
                    for field, prop in schemas[name].get("properties", {}).items():
                        if any(not _bounded(s) for s in _string_schemas(prop)):
                            problems.append(f"{name}.{field}")
            for param in op.get("parameters", []):
                if param["in"] == "cookie":  # размер кук ограничивает nginx
                    continue
                if any(not _bounded(s) for s in _string_schemas(param["schema"])):
                    problems.append(f"{method.upper()} {path}: параметр {param['name']}")

    assert not problems, "Строки без ограничения длины или формата:\n" + "\n".join(problems)