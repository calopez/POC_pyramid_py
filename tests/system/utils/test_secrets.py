"""Test secrets reader."""
# Standard Library
import os

from tm.utils import secrets


def test_read_local_secrets():
    """Read file referred by a relative path."""
    data = secrets.read_ini_secrets("conf/test-secrets.ini", strict=False)
    assert data.get("authentication.secret") == "xxx"


def test_file_secrets():
    """Read file referred by absolute path."""
    data = secrets.read_ini_secrets("file://" + os.path.abspath("conf/test-secrets.ini"), strict=False)
    assert data.get("authentication.secret") == "xxx"
