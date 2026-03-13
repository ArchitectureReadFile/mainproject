from fastapi import HTTPException

from errors.error_codes import ErrorCode


class AppException(Exception):
    """
    서비스 레이어에서 발생하는 도메인 예외입니다.
    라우터의 exception_handler 또는 미들웨어에서 HTTPException으로 변환합니다.
    """

    def __init__(self, error_code: ErrorCode):
        self.error_code = error_code
        self.code = error_code.code
        self.status_code = error_code.status_code
        self.message = error_code.message
        super().__init__(self.message)

    def to_http_exception(self) -> HTTPException:
        return HTTPException(
            status_code=self.status_code,
            detail={"code": self.code, "message": self.message},
        )
