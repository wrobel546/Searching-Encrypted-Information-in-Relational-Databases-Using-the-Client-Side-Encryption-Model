# Wyszukiwanie zaszyfrowanych danych w relacyjnej bazie


## Uruchomienie krok po kroku

1. Utwórz środowisko Python i zainstaluj projekt:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
   ```

2. Uruchom bazę danych:

   ```powershell
   docker compose up -d --wait --wait-timeout 120
   ```

3. Sprawdź połączenie:

   ```powershell
   .\.venv\Scripts\python.exe -m cse_benchmark check-db
   ```

   Jeśli wszystko działa, zobaczysz: `PostgreSQL connection OK (SELECT 1 = 1).`

4. Uruchom testy:

   ```powershell
   .\.venv\Scripts\python.exe -m pytest
   ```

   Test połączenia z prawdziwą bazą jest domyślnie pomijany. Aby go uruchomić, wpisz:

   ```powershell
   $env:CSE_TEST_DB = "1"
   .\.venv\Scripts\python.exe -m pytest
   Remove-Item Env:CSE_TEST_DB
   ```

## Dane do połączenia


| Ustawienie | Wartość | Zmienna środowiskowa |
| --- | --- | --- |
| Adres | `127.0.0.1` | `PGHOST` |
| Port | `5432` | `PGPORT` |
| Nazwa bazy | `cse_benchmark` | `PGDATABASE` |
| Użytkownik | `cse` | `PGUSER` |
| Hasło | `cse_local` | `PGPASSWORD` |
