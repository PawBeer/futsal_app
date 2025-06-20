1. Use case [aktor: Admin]
- cel: Planowanie cotygodniowych meczów z listą głównych i rezerwowych 
system przedstawia wszystkich zawodników, którzy są wpisani na listę 
można dzięki niemu dopisywać kolejnych zawodników i rezerwowych 
można wyłączać określony mecz jeśli z jakiejś przyczyny nie może się odbyć 

2. Use case [aktorzy: System, Zawodnik]
- cel: Umożliwienie zawodnikowi rezygnacji z meczu (przez wysłanie przez system maila z tokenem
link do odmowy jest ważny do 48h przed meczem 
jeżeli zawodnik chce zrezygnować tuż przed meczem to musi zalogować się na swoje konto i zaznaczyć nieobecność 

3. Use case [aktor: System]
- cel: wysyłanie maili z aktualizacjami i kosztami
na podstawie liczby odbytych meczów, w których zawodnik brał udział każdy, kto zagrał co najmniej raz dostaje maila z kwotą do zapłaty (jeśli nie udało się znaleźć zastępcy to koszta ponosi stały zawodnik) 

4. Use case [aktorzy: System, Rezerwowi]
- cel: Wysyłanie maila do rezerwowych z zapytaniem, czy zagrają 
zastanowić się, czy lepiej jest wysłać maila do wszystkich i na jakiejś podstawie robić listę oczekujących, czy jednak wysyłać pojedynczy mail do kogoś, gdy slot się zwolni 
po potwierdzeniu udziału zawodnik rezerwowy może zrezygnować poprzez kontakt z adminem (lub konto w systemie)? 
zapytanie powinno zostać powtórzone jeżeli nadal jakiś slot jest nieobsadzony, a zawodnik nie potwierdził udziału 

5. Use case [aktorzy: System, Zawodnik]
- cel: Każdy zawodnik ma dostęp do swojego konta i może przez odkliknięcie ustawić, że nie może zagrać przez kilka meczów 



* Extra Features: 
  - punkty zajebistości 
  - Extra feature: i18n
