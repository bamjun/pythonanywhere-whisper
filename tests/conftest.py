import os
import sys
import warnings

import django
import pytest

# Add the src directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "_core.settings")
django.setup()

warnings.filterwarnings("ignore", category=DeprecationWarning, module="pydantic")


def pytest_configure(config: pytest.Config) -> None:
    """pytest 설정을 구성합니다."""
    warnings.filterwarnings(
        "ignore", category=DeprecationWarning, module="ninja.signature.utils"
    )

    warnings.filterwarnings(
        "ignore", category=DeprecationWarning, module="pydantic._internal._config"
    )
