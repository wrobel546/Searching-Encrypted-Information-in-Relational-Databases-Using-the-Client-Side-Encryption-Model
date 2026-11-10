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


## Klucze lokalne

Utwórz klucze jednorazowo:

```powershell
python -c "from cse_benchmark.keys import create_keys_file; create_keys_file()"
```

Plik `secrets/keys.json` zawiera osobne klucze szyfrowania
i indeksowania. Jest pomijany przez Git.

Aplikacja odczytuje klucze przez `load_keys()`.
Brak lub niepoprawna zawartość pliku powoduje błąd.
Istniejący plik nie jest automatycznie nadpisywany.

Do odczytu wcześniejszych szyfrogramów potrzebny jest pierwotny
klucz szyfrowania. Nie usuwaj ani nie zastępuj pliku kluczy,
jeśli chcesz zachować możliwość odczytu danych.

Testy kluczy, w tym odczytu po ponownym uruchomieniu Pythona:

```powershell
python -m pytest tests/test_keys.py -v
```


## Scenariusze danych benchmarku

Generowanie:

    python -m cse_benchmark generate-datasets

Zbiory: 1 000, 10 000 i 100 000 rekordów.
Dla każdego rozmiaru generowane są rozkłady uniform i skewed.
Domyślny seed: 42. Wersja scenariuszy: 1.

Generator rezerwuje jeden rekord dla UnikatowyTestowy i trzy
rekordy dla RzadkiTestowy.

W rozkładzie uniform pozostałe rekordy są dzielone możliwie
równomiernie między dziesięć bazowych nazwisk.

W rozkładzie skewed nazwisko Nowak otrzymuje połowę pozostałych
rekordów, z zaokrągleniem w dół. Reszta jest dzielona możliwie
równomiernie między pozostałe dziewięć nazwisk.

Wspólne zapytania:
- zero: NieobecnyTestowy;
- one: UnikatowyTestowy;
- few: RzadkiTestowy;
- many: Nowak, z dodatkowymi spacjami i wielkimi literami.

Każdy zbiór zawiera oczekiwane identyfikatory wyników.
Manifest zawiera konfiguracje, liczebności wyników, wersję Pythona
oraz sumy SHA-256 wygenerowanych plików.

Strategie A, B i C należy porównywać na tych samych kontaktach
i zapytaniach w obrębie scenariusza.

Generowanie danych i sprawdzanie poprawności należy wykonywać
poza pomiarem czasu wyszukiwania.