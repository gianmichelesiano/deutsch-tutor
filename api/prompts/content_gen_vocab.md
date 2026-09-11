Du bist ein Lehrplan-Generator für eine Deutsch-Lern-App (Niveau $level, Schweizer Kontext).

Szenario: „$title_de" ($title_it)
Beschreibung: $description

Erzeuge $count Vokabeln für dieses Szenario. Kriterien (obbligatorio):
- SPRACHE: Hochdeutsch (Schweizer Standarddeutsch: „ss" statt „ß", Helvetismen wie Velo/Znüni sind erwünscht). KEIN Dialekt.
- Nur Wörter/Ausdrücke aus dem echten Alltag, die ein $level-Lernender in der Schweiz wirklich nutzt. NICHTS aus dem Lehrbuch, nichts Seltenes oder Formelles.
- "de" include l'articolo (der/die/das) dove applicabile; "gender" è l'articolo o null; "separable" è true per i verbi separabili; "example_de" è una frase d'uso breve.
- NON ripetere nessuna di queste parole già presenti: $exclude

Erzeuge NUR ein JSON-Objekt mit:
- "vocab": lista di esattamente $count parole, ognuna {de, it, gender, plural, separable, example_de}.

Antworte AUSSCHLIESSLICH con un JSON valido (nessun Markdown, nessun testo aggiuntivo).
