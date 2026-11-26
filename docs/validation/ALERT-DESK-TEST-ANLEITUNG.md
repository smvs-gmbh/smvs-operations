# Alert Desk — praktische TEST-Anleitung

Stand 2026-11-26, CHG-021. Anleitung für den synthetischen Pilotversuch;
keine Erklärung einer abgeschlossenen Systemvalidierung. Das ausführliche
[Prüfprotokoll mit 20 Prüffällen](ALERT-DESK-TEST-VALIDATION.md) enthält
Soll-Ergebnisse, Risiken und Anforderungen an die Nachweise.

## Zugänge

**End User und MAH:**
`https://node221862-env-1900268.jcloud.ik-server.com/alerts`.
Dieser Zugang ist öffentlich per HTTPS erreichbar. Testpersonen brauchen dafür
keinen OpenVPN-Client. Sie benötigen trotzdem eine gültige Einladung und den
Bestätigungscode für den zugeordneten Kontakt. Die Startseite allein gibt keine
Falldaten frei. Es werden nur synthetische Fälle verwendet.

**SMVS/NMVO:** Operations ist nicht öffentlich freigegeben. Für den ersten
Test verwendet der Betreiber einen SSH-Tunnel mit seinem bestehenden SSH-Zugang:

```sh
ssh -N -L 127.0.0.1:8025:127.0.0.1:8016 -p 3022 221862-9004@gate.jpc.infomaniak.com
```

Danach `http://localhost:8025` öffnen. Die zusätzliche Anmeldung mit einem
TEST-Passkey bleibt erforderlich. Das synthetische Administratorkonto heisst
`nmvo@example.test`; der erste persönliche Registrierungsschlüssel liegt
geschützt auf dem Server unter
`/var/lib/jelastic/vcs/smvs-operations-test/private/staff-invitation.txt`.
Er wird über den vertrauenswürdigen Betreiberzugang abgerufen und gehört weder
in Git noch in Screenshots oder Prüfprotokolle. Ein PROD-Passkey wird nicht kopiert.
Ein späterer privater HTTPS-Zugang über VPN ist noch nicht eingerichtet.

**Mail:** Zunächst erfolgt ausschliesslich Aufzeichnung im privaten TEST-Postfach
auf dem Server, nicht Versand ins Internet. Einladung und Code werden dort als
geschützte `.eml`-Dateien unter `private/mail/` abgelegt. Der Betreiber kann sie
über SSH/SFTP lesen. Es gibt kein öffentliches Postfach. Für selbständige externe
Tests muss zuerst der Versand an ausdrücklich festgelegte Testempfänger
eingerichtet und geprüft werden. Die synthetischen `example.test`-Adressen sind
keine zustellbaren Internetpostfächer.

## Vorbereitung durch den Testleiter

1. Installierten Commit, Schema, Konfiguration und Fixture-IDs im Prüfprotokoll
   festhalten. Den tatsächlichen Deployment-Nachweis hinzunehmen; die Versionsnummer
   des Dokuments ist keine Softwareversion.
2. TEST-Banner und synthetische Daten prüfen. VerifyIt bleibt unter
   `https://env-1900268.jcloud.ik-server.com` separat erreichbar.
3. Als NMVO anmelden. Die synthetischen CRM-Kontakte und deren Zuweisungen als
   Alert-Kontakte prüfen. End User und MAH jeweils in einem eigenen Browserprofil
   testen, damit Sitzungen nicht vermischt werden.
4. In Operations eine Einladung für den vorgesehenen Testkontakt erzeugen.
   Einladung im Teilnehmer-Browser öffnen und den passenden Code aus dem
   TEST-Postfach verwenden. Keine internen Bearer- oder Fixture-Sitzungen einsetzen.
5. Vor formaler Prüfung die Fristenregel freigeben: Der lokale Pilot verwendet
   standardmässig drei Werktage ab Anfrage; das dokumentierte fachliche Ziel von
   zwei Arbeitstagen ab Alert ist damit noch nicht abgestimmt. Ohne Festlegung
   sind Fristenprüfungen Beobachtungen, keine formale Abnahme.

## Erster fachlicher Durchlauf

1. **End User:** Einen A2-/A3-Fall öffnen. Packungsdaten und die angezeigten
   Hinweise mit dem synthetischen Ausgangsfall vergleichen. Eigene Ursache mit
   CAPA und Kommentar melden; in einem anderen Fall „Still investigating“ oder
   „Root cause not on my side“ wählen. Ergebnis neu laden und vergleichen.
2. **Vorlagen:** Über „Templates“ einen Kommentar einfügen; Text ergänzen.
   Den aktuellen Kommentar als Vorlage speichern. Auf „My templates“ bearbeiten
   und zum gleichen Fall zurückkehren. Ungesendete Eingaben dürfen nicht verloren
   gehen. Eine spätere Vorlagenänderung darf keinen bereits gesendeten Kommentar
   verändern. Mit einem anderen Kontakt darf diese private Vorlage nicht sichtbar sein.
3. **MAH:** Im eigenen Browserprofil die eigenen Fälle und passenden
   Upload-/Seriennummernprüfungen bearbeiten. Prüfen, dass interne NMVO-Notizen
   und fremde Organisationen nicht sichtbar werden.
4. **NMVO:** Die beiden Rückmeldungen getrennt in RCA prüfen. Einen zulässigen
   Fall mit Entscheidungsgrundlage schliessen und wieder öffnen. Teilnehmer dürfen
   mit ihrer Rückmeldung nicht selbst den lokalen Case schliessen. Fremd geführte
   Fälle und unklare Zuständigkeit separat prüfen.
5. **Sammelbearbeitung:** Den angezeigten Umfang vor Bestätigung prüfen.
   Nur die ausgewählten zulässigen Alerts dürfen geändert werden. Mit zwei
   Browsern eine zwischenzeitliche Änderung provozieren; veraltete Eingaben müssen
   zurückgewiesen bzw. zur erneuten Prüfung vorgelegt werden.
6. **Fristen/Erinnerungen:** Nach Freigabe der Regel getrennte Anfragen für
   End User und MAH erstellen. Wochenendübergang, Fortschrittsmeldung, überfällige
   Antwort, Empfängervorschau und wiederholtes Senden prüfen. Zeitgrenzen nur mit
   kontrollierten Testdaten simulieren, nicht die Serveruhr verstellen.

## Nachweis je Prüffall

Im vollständigen Protokoll pro AD-T-Prüffall dokumentieren:

| Feld | Eintrag |
| --- | --- |
| Prüffall, Software-Commit und Datensatzversion | Ausfüllen |
| Tester, Rolle und Zeitpunkt in UTC | Ausfüllen |
| Tatsächlich ausgeführte Schritte | Ausfüllen |
| Erwartetes / tatsächliches Ergebnis | Ausfüllen |
| Ergebnis | Bestanden / Fehlgeschlagen / Blockiert / Nicht ausgeführt |
| Nachweis / Abweichungsnummer / Wiederholungsprüfung | Verknüpfen |
| Review und Entscheidung | Ausfüllen |

Fehler mit Alert-ID, Rolle, Schritten und erwarteter Wirkung erfassen. Keine
Einladungslinks, Codes, Sitzungscookies oder sonstigen Geheimnisse abbilden.
Fehlgeschlagene Erstprüfungen erhalten; erfolgreiche Wiederholungen ergänzen.
Vor einem Reset zuerst Nachweise sichern. Ein bestandener fachlicher Durchlauf
ersetzt weder Rollen-/Ausfall-/Wiederherstellungsprüfungen noch die formale
Review- und Freigabeentscheidung. Eine TEST-Abnahme schaltet PROD nicht frei.
