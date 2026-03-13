class ServiceException(Exception):
    """Base exception for all service-related errors."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class NotFoundException(ServiceException):
    """Exception raised when a resource is not found."""
    pass

class UnauthorizedException(ServiceException):
    """Exception raised for unauthorized access."""
    pass

class ForbiddenException(ServiceException):
    """Exception raised when access is forbidden."""
    pass

class BadRequestException(ServiceException):
    """Exception raised for invalid requests."""
    pass
