import pytest

pytestmark = pytest.mark.usefixtures("test_env", "clean_auth")
