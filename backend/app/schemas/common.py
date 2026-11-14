from pydantic import AfterValidator


def _no_nul(value: str) -> str:
    # Postgres не принимает \x00 в тексте, иначе вместо 422 получили бы 500
    if "\x00" in value:
        raise ValueError("Недопустимый символ")
    return value


NoNul = AfterValidator(_no_nul)