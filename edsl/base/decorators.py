def polly_command(func):
    """Decorator to mark methods as available commands"""
    func._is_polly_command = True
    return func
