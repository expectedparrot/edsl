import logging

import edsl.logger as edsl_logger


def test_edsl_logger_does_not_install_file_handler_by_default():
    assert not any(
        isinstance(handler, logging.FileHandler)
        for handler in edsl_logger.logger.handlers
    )
