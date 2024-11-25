# FTP

https://el.us.edu.pl/wnst/mod/assign/view.php?id=111629&action=editsubmission

przenoszenie to nie rename from/to. Powinno być kopiuj if success then remove

robimy komendy linux'owe ls, mv, mkdir itd.

możemy użyć bibliotek do parsowania adresów url (url z loginem hasłem, numerem portu, serwerem)

sockety TCP
dwa połączneis: sterujące i do przesyłu
do sterujących jes używany NVT

jak rozpoznać czy wysyła 1/więcej komunikatów powitalnych.
dopiero po możemy wysyłać
każde poleceniu ma odpowiedź od servera
kod, znacznik kontunuacji(more), opis (dla użytkownika lub zinterpretować - gdy są to parametry)
kody to 3-cyfrowe numery. zależnie od pierwsej cyfry wiemy czy powodzenie czy nieudane

nie można curl, ani bibliotek ftp

każda sekewncja konczy się clrm (?)

1xx oczekuje dalszego działania

2xx sukces

3xx wstępny sukces, wumagane dalsze działanie

4xx 5xx - błędy

logowanie nie jest wymagane dla każdego użytkownika, nie zawsze trzeba się logować

FileZilla. Nie bundle tylko czysta instalacja: Więcej opcji : ...
konfikguracja servera >> plain ftp żeby pozwalało ustawić

- mkdir -> mkd
  rmdir - rmd
  rm -> dele
  cp -> stor/retr + pasv
  mv - stor/retr + dele + pasv
  ls - list + pasv

## Treść zadania

Celem zadania jest napisanie podstawowej aplikacji klienckiej FTP. Klient będzie działał w wierszu poleceń i musi obsługiwać sześć następujących operacji: wyświetlanie katalogów (ls), tworzenie katalogów (mkdir), usuwanie plików (rm), usuwanie katalogów (rmdir), kopiowanie plików do i z serwera FTP (cp) oraz przenoszenie plików do i z serwera FTP (mv).

Szczegółowy opis zadania jest dostępny po wybraniu opcji przesłania rozwiązania.

Proszę przesłać kod źródłowy jako oddzielny, nieskompresowany plik.

Klient FTP musi zostać uruchomiony w wierszu poleceń, stosując następującą składnię:

usftp [operacja] [param1] [param2]

operacja to ciąg znaków określający, jaką operację próbuje wykonać użytkownik. Prawidłowe operacje to ls, mkdir, rm, rmdir, cp i mv. Każda operacja wymaga jednego lub dwóch parametrów, oznaczonych w wierszu poleceń jako param1 i param2.

param1 i param2 to ciągi znaków reprezentujące ścieżkę do pliku w lokalnym systemie plików lub adres URL pliku lub katalogu na serwerze FTP.

Na URL składa się: ftp://użytkownik:hasło@adres_serwera:port/katalog/plik.ext

Przykładowe polecenie przeniesienia pliku test.txt z lokalnego systemu plików na serwer FTP, do katalogu test/:
usftp cp c:\katalog\plik.txt ftp://user:pass@127.0.0.1:21/test/

lub np.

usftp cp -u=user -p=pass -o=21 -s=c:\katalog\plik.txt -d=ftp://127.0.0.1/test/

(Nie)dozwolone biblioteki

Częścią wyzwania związanego z tym zadaniem jest to, że wszystkie żądania i odpowiedzi FTP muszą zostać napisane przez studenta od podstaw. Innymi słowy, należy samodzielnie zaimplementować protokół FTP. Można używać dowolnych dostępnych bibliotek do tworzenia połączeń z gniazdami i analizowania adresów URL. Nie można jednak używać żadnych bibliotek/modułów/itp. które implementują protokół FTP. Oczywiście kod nie może również wywoływać narzędzi systemowych implementujących FTP, takich jak ftp lub curl.

Szczegóły zadania

W tym zadaniu należy stworzyć klienta FTP. Ten klient musi mieć możliwość zalogowania się do zdalnego serwera FTP i wykonania kilku operacji na zdalnym serwerze. W tej sekcji zostanie wyjaśnione jak połączyć się z serwerem FTP, opisany zostanie format żądań i odpowiedzi protokołu FTP oraz polecenia FTP, których obsługa jest wymagana.

Aby połączyć się z serwerem FTP, klient będzie musiał otworzyć gniazdo TCP. Domyślnie serwery FTP nasłuchują na porcie 21, chociaż użytkownicy mogą zastąpić port domyślny, podając inny w wierszu poleceń. Gdy klient połączy gniazdo TCP ze zdalnym serwerem, rozpocznie wymianę żądań i odpowiedzi w formacie tekstowym z serwerem FTP.

Wszystkie żądania FTP mają postać:

KOMENDA <param> <...>\r\n

KOMENDA to zazwyczaj trzy- lub czteroliterowe polecenie pisane wielkimi literami, które nakazuje serwerowi FTP wykonanie jakiejś akcji. W zależności od tego, jakie polecenie zostanie wysłane, mogą być wymagane również dodatkowe parametry. Należy pamiętać, że parametry nie powinny być otoczone symbolami < i >; używane są one tylko do oznaczenia elementów komendy, które są opcjonalne. Wszystkie żądania FTP kończą się \r\n.

Po każdym żądaniu serwer FTP odpowie co najmniej jedną odpowiedzią. Niektóre żądania spowodują dwie lub więcej odpowiedzi. Dodatkowo serwery FTP wysyłają wiadomość powitalną po otwarciu połączenia TCP, zanim klient wyśle jakiekolwiek żądania. Wszystkie odpowiedzi FTP mają postać:

KOD <wyjaśnienie czytelne dla człowieka> <param>\r\n

KOD to trzycyfrowa liczba całkowita określająca, czy serwer FTP był w stanie zrealizować żądanie.

Kody 1XX wskazują, że oczekiwane jest dalsze działanie (np. oczekiwanie na pobranie lub przesłanie pliku);

Kody 2XX oznaczają sukces;

Kody 3XX oznaczają wstępny sukces, ale wymagane są dalsze działania (np. Twój klient wysłał nazwę użytkownika, ale teraz wymagane jest prawidłowe hasło);

Kody 4XX, 5XX i 6XX wskazują, że wystąpił błąd.

Więcej szczegółów na temat kodów odpowiedzi FTP można znaleźć tutaj. Niektóre serwery dołączają do każdej odpowiedzi opcjonalne, czytelne dla człowieka wyjaśnienie, które wyjaśnia, co się stało lub czego serwer oczekuje od klienta. Te komunikaty, czytelne dla człowieka, są przydatne do celów debugowania. Odpowiedzi mogą zawierać także parametr niezbędny do działania klienta (przede wszystkim dla komendy PASV - patrz niżej). Wszystkie odpowiedzi FTP kończą się \r\n. Niektóre, ale nie wszystkie, zawierają kropkę przed \r\n.

Tworzony klient FTP musi mieć możliwość wysyłania co najmniej następujących poleceń FTP:

USER <nazwa użytkownika>\r\n
Zaloguj się do serwera FTP używając podanej nazwy użytkownika. Jeśli użytkownik nie określi nazwy użytkownika w wierszu poleceń, klient może założyć, że nazwa użytkownika jest „anonymous”. Jest to pierwsze żądanie, które klient musi wysłać do serwera FTP.

PASS <hasło>\r\n
Zaloguj się do serwera FTP przy użyciu podanego hasła. Jeśli użytkownik podał hasło w wierszu poleceń, jest to drugie żądanie, które klient musi wysłać do serwera FTP. Jeśli użytkownik nie podał hasła w wierszu poleceń, klient może pominąć to żądanie.

TYPE I\r\n
Ustaw połączenie na 8-bitowy tryb danych binarnych (w przeciwieństwie do 7-bitowego ASCII lub 36-bitowego EBCDIC). Klient powinien ustawić TYPE przed próbą przesłania lub pobrania jakichkolwiek danych.

MODE S\r\n
Ustaw połączenie na tryb strumieniowy (w przeciwieństwie do blokowego lub skompresowanego). Klient powinien ustawić MODE przed próbą przesłania lub pobrania jakichkolwiek danych.

STRU F\r\n
Ustaw połączenie na tryb zorientowany na plik (w przeciwieństwie do zorientowanego na rekord lub stronę). Klient powinien ustawić STRU przed próbą przesłania lub pobrania jakichkolwiek danych.

LIST <ścieżka do katalogu>\r\n
Wyświetl zawartość podanego katalogu na serwerze FTP. Odpowiednik ls w wierszu poleceń systemu Unix.

DELE <ścieżka do pliku>\r\n
Usuń podany plik na serwerze FTP. Odpowiednik rm w wierszu poleceń systemu Unix.

MKD <ścieżka do katalogu>\r\n
Utwórz katalog pod podaną ścieżką na serwerze FTP. Odpowiednik mkdir w wierszu poleceń systemu Unix.

RMD <ścieżka do katalogu>\r\n
Usuń katalog o podanej ścieżce na serwerze FTP. Odpowiednik rm -d w wierszu poleceń systemu Unix.

STOR <ścieżka do pliku>\r\n
Prześlij nowy plik o podanej ścieżce i nazwie na serwer FTP.

RETR <ścieżka do pliku>\r\n
Pobierz plik o podanej ścieżce i nazwie z serwera FTP.

QUIT\r\n
Poproś serwer FTP o zamknięcie połączenia.

PASV\r\n
Poproś serwer FTP o otwarcie kanału danych.

Kanał sterujący, kanał danych

Protokół FTP jest nieco nietypowy, ponieważ wymaga nie jednego, ale dwóch połączeń przez gniazda. Pierwsze gniazdo, które klient otworzy dla serwera FTP, nazywane jest kanałem sterującym. Kanałem sterującym jest zazwyczaj połączenie z portem 21 na serwerze FTP. Kanał strujący służy do wysyłania żądań FTP i odbierania odpowiedzi FTP. Jednakże żadne dane (pliki) nie są przesyłane ani pobierane w kanale sterującym. Aby pobrać jakiekolwiek dane (np. plik lub listę katalogów) lub przesłać jakiekolwiek dane (np. plik), klient musi poprosić serwer o otwarcie kanału danych na drugim porcie.

Poleceniem FTP otwierającym kanał danych jest PASV. Klient wysyła PASV do serwera FTP, a on odpowiada komunikatem wyglądającym mniej więcej tak:

227 Entering passive mode (192,168,150,90,195,149).

Kod 227 oznacza sukces. Sześć liczb w nawiasach to adres IP i port, do którego klient powinien podłączyć gniazdo TCP/IP, aby utworzyć kanał danych. Pierwsze cztery cyfry to adres IP (w tym przykładzie 192.168.150.90), a dwie ostatnie liczby to port. Numery portów są 16-bitowe, więc dwie liczby reprezentują odpowiednio górne i dolne 8 bitów numeru portu. W tym przykładzie numer portu to (195 « 8) + 149 = 50069.

Po zakończeniu przesyłania danych kanał danych musi zostać zamknięty przez nadawcę. Zmienia się to, kto zamyka kanał. Jeśli serwer wysyła dane (np. pobrany plik lub listę katalogów), to serwer zamknie gniazdo danych po wysłaniu wszystkich danych. W ten sposób klient wie, że wszystkie dane zostały przesłane. Alternatywnie, jeśli klient wysyła dane (np. przesyła plik), to klient musi zamknąć gniazdo danych po wysłaniu wszystkich danych. W ten sposób serwer wie, że wszystkie dane zostały odebrane. Jeśli klient chce przesłać lub pobrać dodatkowe dane, np. wykonać wiele operacji podczas jednej sesji kanału sterującego, wówczas na każdą operację należy otworzyć jeden kanał danych PASV.

Należy pamiętać, że kanał sterujący (tj. pierwsze gniazdo) musi pozostać otwarty, tak długo jak kanał danych jest otwarty. Po zamknięciu kanału danych klient może zakończyć sesję FTP, wysyłając polecenie QUIT do serwera FTP w kanale sterującym i zamykając gniazdo kontrolne.

Język

Kod klienta FTP można napisać w dowolnym języku programowania, wedle uznania Autora. Nie wolno używać bibliotek, które są niedozwolone w tym projekcie. Rozwiązanie powinno zawierać kod źródłowy oraz plik wykonywalny (jeśli wybrany język jest kompilowany).

Na przykład, jeśli klienta FTP będzie napisany w Pythonie, dozwolone będą następujące moduły: socket i urllib.parse. Jednakże te moduły nie będą dozwolone: ​​urllib.request, ftplib i pycurl.

Sugerowane podejście do projektu

Rozpoczynając pracę nad tym projektem, zalecam wdrożenie wymaganych funkcji w następującej kolejności.

Analiza (parsowanie) wiersza poleceń. Należy zacząć od napisania programu, który pomyślnie implementuje wymaganą składnię wiersza poleceń i potrafi analizować przychodzące dane, np. adresy URL FTP.

Ustanowienie połączenia. Należy dodać obsługę łączenia się i logowania do serwera FTP. Obejmuje to ustanowienie kanału sterującego TCP, prawidłowe wysyłanie poleceń USER, PASS, TYPE, MODE, STRU i QUIT. Należy wyprowadzić na konsolę odpowiedzi z serwera, aby potwierdzić, że każde polecenie zostało odebrane i poprawnie zinterpretowane.

MKD i RMD. Należy zaimplementować obsługę tworzenia i usuwania zdalnych katalogów. Polecenia te są prostsze, ponieważ nie wymagają kanału danych. Należy sprawidzić, czy klient działa poprawnie, używając lokalnego serwera FTP, aby dokładnie sprawdzić wyniki.

> MKD i RMD, DEL nie wymagają połączenia danych, wystarczy sterujące
> W odpowiedzi na PASS server otwiera losowy port i wysyła doo jakiego portu należy utworzyć ppołączenie danych. Koniec operacji przesyłania jest oznaczane przez zamknięcie połączenia przez stronę wysyłającą

PASV i LIST. Nalezy zaimplementować obsługę tworzenia kanału danych, a następnie polecenie LIST, aby przetestować kanał danych.

STOR, RETR i DELE. Należy uzupełnić swojego klienta, dodając obsługę przesyłania, pobierania i usuwania plików. Nalezy dokładnie sprawdzić implementację, porównując ją z wynikami "standardowego" klienta FTP.

---

# Scenariusze testowania

server może nie chceić hasła

może nie móc otworzyć połączenia danych (brak dostępnych portów na serwezre)

co jak zostanie zresetowane połączenie z serwerem w trakcie?

kilka sesji do servera (klientów)
czy zalogowanie jednego usera nie loguje przypadkiem wszystkich którzy łączą się w tym czasie
