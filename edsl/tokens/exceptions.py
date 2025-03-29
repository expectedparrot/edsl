"""
This module defines the exception hierarchy for the tokens module.

All exceptions related to token usage tracking and cost calculations are defined here.
"""

from ..base import BaseException


class TokenError(BaseException):
    """
    Base exception for all token-related errors.
    
    This is the parent class for all exceptions raised within the tokens module.
    It inherits from BaseException to ensure proper error tracking and reporting.
    """
    pass


class TokenUsageError(TokenError):
    """
    Raised when there is an error in token usage operations.
    
    This exception is raised for issues related to token usage tracking,
    such as invalid token counts or incompatible token usage types.
    """
    pass


class TokenCostError(TokenError):
    """
    Raised when there is an error in token cost calculations.
    
    This exception is used for issues with cost calculations, such as
    missing or invalid pricing information.
    """
    pass