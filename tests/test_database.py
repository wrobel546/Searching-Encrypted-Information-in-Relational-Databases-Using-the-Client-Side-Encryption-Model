import os

import pytest

from cse_benchmark.cli import main


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("CSE_TEST_DB") != "1",
    reason="Set CSE_TEST_DB=1 to test a running PostgreSQL database",
)
def test_check_db_against_postgresql(capsys):
    assert main(["check-db"]) == 0
    output = capsys.readouterr()
    assert "PostgreSQL connection OK (SELECT 1 = 1)." in output.out
    assert output.err == ""
