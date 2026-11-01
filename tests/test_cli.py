import psycopg

from cse_benchmark import cli


def test_check_db_reports_connection_failure(monkeypatch, capsys):
    def unavailable_database():
        raise psycopg.OperationalError("test database is unavailable")

    monkeypatch.setattr(cli, "connect", unavailable_database)

    assert cli.main(["check-db"]) == 1

    output = capsys.readouterr()
    assert output.out == ""
    assert "PostgreSQL connection failed" in output.err