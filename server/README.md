# Server FTP

## Scenariusze testowania

- [ ] co gdy jeden user się zaloguje, czy drugi łączący się jeż just zalogowany
- [ ] czy ktoś może się połączyć do nie swojej sesji
- [x] user nie może wyjść ponad swój katalog domowy (parser ścieżek obsługuje i względne i bezwzględne, ale obie muszą być względem katalogu domowego)
- [x] if transfer in data connection doesn't start after eg. 10s -> close data conn
- [x] co jak nie ma config file (try:)
- [ ] ~~utwórz brakujące foldery pośrednie (przy tworzeniu katalogów) /istnieje/nie/nie/target~~
- [x] żeby nie wyszedł ponad nie tylko główny folder ale i folder usera
- [x] powinien pokazywać ścieżkę jako absolutną ale względem folderu głównego
- [x] da się jakoś przez dwukropek dostać~wyżej?
- [x] specyfikacja mówi jakie MUSZĄ być MODE, STRU, TYPE https://datatracker.ietf.org/doc/html/rfc959#section-5 . TYPE I - image/binary, ASCII do tekstu; STRU wystarczy nam file
- [x] NOP polecenie do podtrzymania sesji tylko
- [x] jak klient się połączy ale nie zaloguje to zamknięcie sesji.
- [x] tak samo po zalogowaniu ale bez aktywności (tu dłuższy czas)
- [ ] timeout for data transfer time?

---

## Treść zadania

Zadanie polega za implementacji prostego serwera FTP dla sieci IPv4, w dowolnie wybranym języku programowania. Implementacja protokołu FTP nie musi być pełna ale nie może wykorzystywać gotowej kontrolki FTP, tylko musi bazować na surowych gniazdach (socket) TCP.

Proszę przesłać kod źródłowy jako oddzielny, nieskompresowany plik.

Serwer powinien obsługiwać **przynajmniej**:

- [x] tryb pasywny (PASV),
- [x] określenie listy portów TCP dla połączeń trybu pasywnego,
- [x] jednego użytkownika z hasłem,
- [x] użytkownika anonimowego,
- [x] wysyłanie listy plików,
- [x] wysyłanie oraz odbieranie pliku.

W wariancie optymalnym powinien umożliwiać:

- [x] logowanie użytkowania (USER, PASS),
- [x] pobieranie bieżącego katalogu (PWD),
- [x] zmianę katalogu w górę (CDUP),
- [x] wchodzenie do katalogu (CWD),
- [x] tworzenie i usuwanie katalogu (MKD, RMD),
- [x] pobieranie listy plików (LIST),
- [ ] wysyłanie, pobieranie i usuwanie pliku (STOR, RETR, DELE).

Konfiguracja serwera może się odbywać z linii poleceń lub za pośrednictwem czytelnego dla człowieka pliku konfiguracyjnego.Konfiguracja powinna umożliwiać:

- [x] określenie katalogu głównego FTP w lokalnym systemie plików,
- [x] wskazania nazwy i hasła użytkownika,
- [x] włączenie lub zablokowanie dostępu anonimowego,
- [x] określenie puli portów TCP dla połączeń pasywnych (np. min, max),
- [x] określenie interfejsu (adresu IP) na którym serwer będzie nasłuchiwał połączeń (domyślnie, na wszystkich aktywnych, adres IP 0.0.0.0).

Szczególną uwagę proszę poświęcić mechanizmowi **autoryzacji oraz obsłudze błędów** - zarówno po stronie procesu serwera, jak i informacji zwrotnej dla klienta. Warto uwzględnić limity czasu nieaktywności przed zalogowaniem i po zalogowaniu.
