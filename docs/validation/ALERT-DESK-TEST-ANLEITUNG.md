# Alert Desk — praktische TEST-Anleitung

Stand 2026-11-26, CHG-021. Anleitung für den synthetischen Pilotversuch;
keine Erklärung einer abgeschlossenen Systemvalidierung. Das ausführliche
[Prüfprotokoll mit 20 Prüffällen](ALERT-DESK-TEST-VALIDATION.md) enthält
Soll-Ergebnisse, Risiken und Anforderungen an die Nachweise.

## Zugänge

**End User und MAH:**
`https://node221862-env-1900268.jcloud.ik-server.com/alerts`.
End User sehen ausschliesslich Alerts ihrer eigenen anfragenden Location-IDs.
Frühere Packungsaktionen und Export-Zuordnungen geben keinen Zugriff.
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
geschützte `.eml`-Dateien unter `private/mail/` abgelegt. Angemeldete TEST-Mitarbeitende öffnen sie über
[Open test mailbox](http://localhost:8025/workflows/alert-desk/mailbox) in Operations.
Die Liste ist nach Eingang sortiert; in der Nachricht öffnet „Open participant
invitation“ den Teilnehmerzugang. Nach Anforderung des Codes die Postfachliste
aktualisieren und die neueste „Verification code“-Nachricht öffnen. Der Zugang
ist nur im privaten Operations verfügbar; es gibt kein öffentliches Postfach. Für selbständige externe
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
   Für A24 „DEMO-A24-1“ den eigenen Versuch untersuchen und Ursache/Fortschritt,
   CAPA und Kommentar erfassen. Eine Rückmeldung ändert keinen Packungsstatus.
   „DEMO-A24-FOREIGN“ ist ein zusätzlicher Negativfall: Er darf auch dann nicht
   sichtbar oder bearbeitbar sein, wenn eine frühere Aktion die eigene Location
   erwähnt. Bestehende Beispiele wurden dafür nicht umgeschrieben.
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


## Ergänzung 2026-11-27: MAH-Sicht und My account (CHG-030)

1. Als MAH über die bekannte TEST-Adresse anmelden. Ohne konkrete Zuweisung
   erscheinen A2/A3/A52; A7/A24/A68 dürfen auch unter All cases, Suche und einem
   alten Direktlink nicht zugänglich sein. Produktzuordnung bleibt Voraussetzung.
2. Als NMVO für einen A7/A24/A68 gezielt beim betreffenden MAH eine Abklärung
   anfordern. Nur dieser aktuelle Alert wird zusätzlich freigegeben, keine
   unangeforderten Schwester-Alerts. Eigene Befunde und NMVO-Entscheid bleiben
   getrennt. Eine Anfrage darf keine andere Organisation freischalten.
3. Im Reiter My account E-Mail, Organisation und Rolle kontrollieren. Diese
   Angaben werden im CRM gepflegt. Vorhandene Passkeys müssen weiterhin sichtbar
   und nutzbar sein; Magic Link bleibt als Alternative bestehen.
4. Nach neuer Anmeldung erscheint die Fallübersicht. Ohne Passkey lässt sich die
   optionale Einrichtung mit Later überspringen. Add passkey führt zur Einrichtung;
   danach zurück zur Fallübersicht mit Bestätigung. Teste den nächsten Login mit
   dem eingerichteten Passkey und mit einem neu angeforderten E-Mail-Link.
5. Nach mehr als zehn Minuten erst beim Versuch, einen Passkey hinzuzufügen oder
   zu widerrufen, erneut anmelden. Danach führt der Ablauf zurück zu My account.
   Beim blossen Lesen darf kein permanenter Warntext zur Anmeldefrist erscheinen.
6. Revoke nur mit einem entbehrlichen Test-Passkey prüfen: Bestätigung verlangt,
   danach alle Sitzungen dieser Organisation/Rolle beendet. Einen tatsächlich
   verwendeten Passkey nicht für diesen Test entfernen.

Erwartung und tatsächliches Ergebnis mit Rolle, Zeit (UTC), Alert-ID und ohne
Links, Codes oder Sitzungstoken protokollieren. Technische Tests ersetzen nicht
die fachliche Abnahme. PROD gehört nicht zu diesem Prüfumfang.


## CHG-030 B — Guided MAH upload outcome (2026-11-27)

Bei A2 als MAH zunächst Still investigating speichern, dann Update findings
öffnen. Solange die Upload-Frage unbeantwortet bleibt, muss der Hinweis erklären,
dass für Root cause not on my side zuerst der bestätigte Batch-Upload (Yes)
benötigt wird. Nach Yes muss diese Ergebniswahl verfügbar sein und gespeichert
werden können. Bei A3 zusätzlich die bestätigte Annahme der Seriennummer prüfen.
No bzw. Other issue on my side muss die entsprechende Einschränkung erklären.
Ein neuer Befund wird ausdrücklich gewählt; frühere Befunde bleiben erhalten.


## CHG-031 — Direkter MAH-Befund und Anhänge (2026-11-27)

Dieser Ablauf ersetzt für MAH A2/A3 die oben beschriebenen Upload-Pflichtfragen.

1. Als MAH A2 und A3 öffnen. Die drei Befunde müssen sofort wählbar sein;
   Batch-/Seriennummer-Upload-Fragen und Fehlerkategorien entfallen.
2. Root cause on my side wählen. Ohne Massnahmenstatus muss Speichern verhindert
   werden. Open, In progress oder Implemented wählen, Kommentar leer lassen und
   speichern. Nach Neuladen müssen Befund und Massnahmenstatus erhalten sein.
3. Zu Root cause not on my side wechseln: kein Massnahmenstatus erforderlich.
   Still investigating ebenfalls ohne Kommentar speichern. Frühere Befunde bleiben
   im Verlauf; der NMVO-Fall wird nicht automatisch geschlossen.
4. Als End User A2/A3 öffnen: A2 fragt nach Übereinstimmung der Charge, A3 nach
   Übereinstimmung der Seriennummer mit der Packung. Prozess-/Handhabungsfehler und
   Scanner-/Softwarefehler bleiben unterscheidbar. Nicht durch einen generischen
   MAH-Befund ersetzen.
5. Ohne Kommentar/Befund eine synthetische TXT-, PDF- oder Bilddatei hochladen.
   Link aufrufen und Inhalt prüfen. Andere Teilnehmerrolle darf diese Datei nicht
   sehen; NMVO muss sie in der Analyse dieses Alerts abrufen können. Ein anderer
   Alert darf über eine kopierte Datei-ID keinen Zugriff erhalten.
6. 5 MiB Grenze, nicht unterstützten Dateityp und fünf Dateien pro Rolle/Organisation/
   Alert-Version prüfen. Dateien bleiben am einzelnen Alert, auch bei Batch-Befund.
   Bei geschlossenen Fällen nur Download; bei neuer Quellversion zeigt die NMVO
   ältere Dateien als frühere Version. Keine vertraulichen Echtdokumente für diese
   technischen Tests verwenden.

Weitere End-User-Fragen weiterhin je Alerttyp fachlich prüfen. Diese Anleitung
ersetzt keine Abnahme der Fälschungsbeurteilung oder QMS-Freigabe.
