Nie można gotowego servera ftp

przynajmniej pasywny tryb

zakres portów dla pasywnego (do skonfigurowania)

user z hasłem i bez (anonimowy) do konfiguracji

co gdy jeden user się zaloguje, czy drugi łączący się jeż just zalogowany

user nie może wyjść ponad swój katalog domowy (parser ścieżek obsługuje i względne i bezwzględne, ale obie muszą być względem katalogu domowego)

jak klient się połączy ale nie zaloguje to zamknięcie sesji.
tak samo po zalogowaniu ale bez aktywności (tu dłuższy czas)

---

# Treśc zadania

Zadanie polega za implementacji prostego serwera FTP dla sieci IPv4, w dowolnie wybranym języku programowania. Implementacja protokołu FTP nie musi być pełna ale nie może wykorzystywać gotowej kontrolki FTP, tylko musi bazować na surowych gniazdach (socket) TCP.

Proszę przesłać kod źródłowy jako oddzielny, nieskompresowany plik.

Serwer powinien obsługiwać przynajmniej: tryb pasywny (PASV) oraz określenie listy portów TCP dla połączeń trybu pasywnego, jednego użytkownika z hasłem, użytkownika anonimowego, wysyłanie listy plików, wysyłanie oraz odbieranie pliku. W wariancie optymalnym powinien umożliwiać: logowanie użytkowania (USER, PASS), pobieranie bieżącego katalogu (PWD), zmianę katalogu w górę (CDUP), wchodzenie do katalogu (CWD), tworzenie i usuwanie katalogu (MKD, RMD), pobieranie listy plików (LIST), wysyłanie, pobieranie i usuwanie pliku (STOR, RETR, DELE). Konfiguracja serwera może się odbywać z linii poleceń lub za pośrednictwem czytelnego dla człowieka pliku konfiguracyjnego. Konfiguracja powinna umożliwiać:

- określenie katalogu głównego FTP w lokalnym systemie plików,
- wskazania nazwy i hasła użytkownika,
- włączenie lub zablokowanie dostępu anonimowego,
- określenie puli portów TCP dla połączeń pasywnych (np. min, max),
- określenie interfejsu (adresu IP) na którym serwer będzie nasłuchiwał połączeń (domyślnie, na wszystkich aktywnych, adres IP 0.0.0.0).
- Szczególną uwagę proszę poświęcić mechanizmowi autoryzacji oraz obsłudze błędów - zarówno po stronie procesu serwera, jak i informacji zwrotnej dla klienta. Warto uwzględnić limity czasu nieaktywności przed zalogowaniem i po zalogowaniu.
