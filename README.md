# Wyszukiwanie zaszyfrowanych informacji w relacyjnych bazach danych

Prototyp badawczy do pracy magisterskiej w modelu Client-Side Encryption.
Pierwszy etap obejmuje projekt Python, lokalny PostgreSQL i sprawdzenie połączenia.
Kolejne etapy dodadzą generator danych, szyfrowanie, strategie wyszukiwania i pomiary.

## Wymagania

- Python 3.11 lub nowszy.
- Docker Desktop z uruchomionym silnikiem kontenerów Linux i Docker Compose v2.
- Wolny lokalny port 5432 (lub inny ustawiony przez `PGPORT`).

Polecenia poniżej wykonuj w głównym katalogu repozytorium, w PowerShell.

## Instalacja

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Projekt używa układu `src/` i instalacji edytowalnej. Polecenia z pełną ścieżką
do Pythona nie wymagają aktywacji środowiska ani zmiany polityki wykonywania skryptów.
Psycopg instalowany jest w wariancie binarnym, zawierającym biblioteki klienta PostgreSQL.
Pytest należy do opcjonalnych zależności `dev`.

## Uruchomienie bazy i sprawdzenie połączenia

```powershell
docker compose up -d --wait --wait-timeout 120
docker compose ps
.\.venv\Scripts\python.exe -m cse_benchmark check-db
```

Compose uruchamia PostgreSQL 17 i czeka na pozytywny healthcheck.
Polecenie `check-db` łączy się z bazą z poziomu Pythona, wykonuje `SELECT 1`
i wypisuje `PostgreSQL connection OK (SELECT 1 = 1).`.
Nieudane połączenie kończy się kodem 1 i komunikatem błędu.

Po aktywacji środowiska dostępne jest też polecenie `cse-benchmark check-db`.

## Konfiguracja

Python i Compose korzystają z tych samych zmiennych środowiskowych:

| Zmienna | Wartość domyślna | Znaczenie |
| --- | --- | --- |
| `PGHOST` | `127.0.0.1` | Adres bazy dla aplikacji Python |
| `PGPORT` | `5432` | Port bazy na hoście |
| `PGDATABASE` | `cse_benchmark` | Nazwa bazy |
| `PGUSER` | `cse` | Użytkownik |
| `PGPASSWORD` | `cse_local` | Hasło lokalnej bazy |

Domyślne dane logowania służą wyłącznie lokalnemu środowisku deweloperskiemu.
Port kontenera jest dostępny tylko pod adresem `127.0.0.1`.
Python ma ustawiony limit oczekiwania na połączenie wynoszący 5 sekund.

Jeśli port 5432 jest zajęty, ustaw nowy port w tej samej sesji PowerShell
przed uruchomieniem Compose i Pythona:

```powershell
$env:PGPORT = "5433"
docker compose up -d --wait --wait-timeout 120
.\.venv\Scripts\python.exe -m cse_benchmark check-db
```

Pozostałe zmienne można ustawiać analogicznie. Python odczytuje zmienne procesu;
nie wczytuje samodzielnie pliku `.env`. Dla spójności konfiguracji używaj zmiennych
sesji PowerShell, które są widoczne również dla Compose.

PostgreSQL zapisuje dane w nazwanym wolumenie `postgres_data` zarządzanym przez Compose.
Zmienne `POSTGRES_*` inicjalizują użytkownika i bazę tylko przy pierwszym uruchomieniu
z pustym wolumenem. Zmiana `PGUSER`, `PGDATABASE` lub `PGPASSWORD` nie zmienia
istniejącego użytkownika ani bazy w już zainicjalizowanym wolumenie.

## Testy

Testy bez wymagania działającej bazy:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Test integracyjny jest domyślnie pomijany. Aby sprawdzić rzeczywiste połączenie,
uruchom PostgreSQL i włącz go w tej samej sesji:

```powershell
$env:CSE_TEST_DB = "1"
.\.venv\Scripts\python.exe -m pytest
Remove-Item Env:CSE_TEST_DB
```

Test integracyjny wykonuje wyłącznie zapytanie odczytowe i nie tworzy tabel.

## Zatrzymanie i diagnostyka

```powershell
docker compose logs --tail 50 postgres
docker compose stop
```

Ponowne uruchomienie: `docker compose up -d --wait --wait-timeout 120`.
Polecenie `docker compose down` usuwa kontener i sieć, zachowując wolumen z danymi.
Gdy Docker zgłasza brak silnika, uruchom Docker Desktop i poczekaj na jego gotowość.

## Dokumentacja narzędzi

- [Konfiguracja pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
- [Instalacja Psycopg](https://www.psycopg.org/psycopg3/docs/basic/install.html)
- [Gotowość usług w Docker Compose](https://docs.docker.com/compose/how-tos/startup-order/)
