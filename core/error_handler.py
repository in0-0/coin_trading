"""
통일된 에러 처리 시스템

이 모듈은 트레이딩 시스템 전체에서 일관된 에러 처리를 제공합니다.
에러 로깅, 알림, 복구 전략을 중앙화하여 코드 중복을 줄입니다.
"""

import logging
import functools
from datetime import datetime
from typing import Callable, Any, Dict, Optional, TypeVar, Union
from contextlib import contextmanager

from .exceptions import TradingError, ValidationError, DataError, StrategyError, OrderError, NetworkError

T = TypeVar('T')

class ErrorHandler:
    """
    통일된 에러 처리 시스템

    에러 로깅, 사용자 알림, 복구 전략을 제공합니다.
    """

    def __init__(self, notifier=None):
        """
        Args:
            notifier: 알림을 보내기 위한 노티파이어 객체 (선택사항)
        """
        self.notifier = notifier
        self.logger = logging.getLogger(__name__)

    def handle_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        notify: bool = True,
        reraise: bool = False,
        log_level: str = "error"
    ) -> bool:
        """
        통일된 에러 처리

        Args:
            error: 발생한 예외
            context: 추가 컨텍스트 정보
            notify: 사용자에게 알림을 보낼지 여부
            reraise: 예외를 다시 발생시킬지 여부
            log_level: 로깅 레벨 ("debug", "info", "warning", "error", "critical")

        Returns:
            복구 성공 여부 (복구 전략이 있는 경우)
        """
        # 컨텍스트 정보 구성
        error_context = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            **(context or {})
        }

        # TradingError의 경우 추가 정보 활용
        if isinstance(error, TradingError):
            error_context.update(error.context)

        # 로깅
        log_message = f"Error occurred: {error}"
        if error_context:
            log_message += f" | Context: {error_context}"

        if log_level == "debug":
            self.logger.debug(log_message, exc_info=True)
        elif log_level == "info":
            self.logger.info(log_message, exc_info=True)
        elif log_level == "warning":
            self.logger.warning(log_message, exc_info=True)
        elif log_level == "critical":
            self.logger.critical(log_message, exc_info=True)
        else:  # error (기본값)
            self.logger.error(log_message, exc_info=True)

        # 사용자 알림
        if notify and self.notifier:
            try:
                notification_msg = f"⚠️ Error: {type(error).__name__}"
                if hasattr(error, 'message'):
                    notification_msg += f"\n{error.message}"
                else:
                    notification_msg += f"\n{str(error)}"

                if context:
                    context_items = [f"{k}: {v}" for k, v in context.items() if k != "error_type"]
                    if context_items:
                        notification_msg += f"\nContext: {', '.join(context_items)}"

                self.notifier.send(notification_msg)
            except Exception as notify_error:
                self.logger.error(f"Failed to send notification: {notify_error}")

        # 복구 전략 적용 (현재는 기본 복구만)
        recovered = self._apply_recovery_strategy(error, error_context)

        if reraise:
            raise error

        return recovered

    def _apply_recovery_strategy(self, error: Exception, context: Dict[str, Any]) -> bool:
        """
        에러별 복구 전략 적용

        Args:
            error: 발생한 예외
            context: 에러 컨텍스트

        Returns:
            복구 성공 여부
        """
        # 네트워크 에러 복구
        if isinstance(error, NetworkError):
            retry_count = context.get("retry_count", 0)
            if retry_count < 3:
                wait_time = 2 ** retry_count  # 지수 백오프
                self.logger.info(f"Network error recovery: waiting {wait_time}s before retry")
                return True

        # 데이터 에러 복구
        elif isinstance(error, DataError):
            # 데이터가 없거나 손상된 경우 기본값으로 복구 시도
            if "no_data" in str(error).lower():
                self.logger.info("Data error recovery: using fallback values")
                return True

        # 전략 에러 복구
        elif isinstance(error, StrategyError):
            # 전략 계산 실패 시 HOLD 신호로 복구
            self.logger.warning("Strategy error recovery: defaulting to HOLD signal")
            return True

        # 검증 에러 복구
        elif isinstance(error, ValidationError):
            # 검증 실패 시 기본값 사용
            self.logger.warning("Validation error recovery: using default values")
            return True

        return False  # 복구 전략 없음

    def safe_execute(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> tuple[bool, Optional[T], Optional[Exception]]:
        """
        함수를 안전하게 실행

        Args:
            func: 실행할 함수
            *args: 함수 인자
            **kwargs: 함수 키워드 인자

        Returns:
            (성공여부, 결과, 예외)
        """
        try:
            result = func(*args, **kwargs)
            return True, result, None
        except Exception as e:
            self.handle_error(e, context={"function": func.__name__})
            return False, None, e

    def create_safe_wrapper(self, log_level: str = "error", notify: bool = True):
        """
        안전 실행 래퍼 팩토리

        Args:
            log_level: 로깅 레벨
            notify: 알림 전송 여부

        Returns:
            함수를 안전하게 실행하는 데코레이터
        """
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    self.handle_error(
                        e,
                        context={"function": func.__name__},
                        notify=notify,
                        log_level=log_level
                    )
                    # 기본값 반환 또는 None
                    if hasattr(func, "__annotations__") and "return" in func.__annotations__:
                        return_type = func.__annotations__["return"]
                        if return_type == bool:
                            return False
                        elif return_type == int:
                            return 0
                        elif return_type == float:
                            return 0.0
                        elif return_type == str:
                            return ""
                    return None
            return wrapper
        return decorator


@contextmanager
def error_handling_context(
    error_handler: ErrorHandler,
    operation: str,
    context: Optional[Dict[str, Any]] = None
):
    """
    에러 처리를 포함한 컨텍스트 매니저

    Args:
        error_handler: 에러 핸들러 인스턴스
        operation: 수행 중인 작업 설명
        context: 추가 컨텍스트 정보
    """
    try:
        yield
    except Exception as e:
        error_context = {"operation": operation, **(context or {})}
        error_handler.handle_error(e, context=error_context)
        raise


# 전역 에러 핸들러 인스턴스
_global_error_handler = None

def get_global_error_handler() -> ErrorHandler:
    """전역 에러 핸들러 반환"""
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler()
    return _global_error_handler

def set_global_error_handler(handler: ErrorHandler):
    """전역 에러 핸들러 설정"""
    global _global_error_handler
    _global_error_handler = handler
