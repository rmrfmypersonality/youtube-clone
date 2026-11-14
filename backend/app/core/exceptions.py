class AppError(Exception):
    status_code = 400
    default_detail = "Ошибка запроса"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class Unauthorized(AppError):
    status_code = 401
    default_detail = "Требуется вход"


class Forbidden(AppError):
    status_code = 403
    default_detail = "Недостаточно прав"


class NotFound(AppError):
    status_code = 404
    default_detail = "Не найдено"


class Conflict(AppError):
    status_code = 409
    default_detail = "Конфликт данных"

class PayloadTooLarge(AppError):
    status_code = 413
    default_detail = "Файл слишком большой"


class UnsupportedMedia(AppError):
    status_code = 415
    default_detail = "Неподдерживаемый тип файла"