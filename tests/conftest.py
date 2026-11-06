import os
import tempfile

import pytest


_test_database_fd, _test_database_path = tempfile.mkstemp(prefix='lamu-tours-tests-', suffix='.db')
os.close(_test_database_fd)
os.unlink(_test_database_path)
os.environ['DATABASE_URL'] = f'sqlite:///{_test_database_path}'

from app import limiter


@pytest.fixture(autouse=True)
def reset_rate_limits():
    limiter.reset()
