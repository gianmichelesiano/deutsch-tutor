Du bist ein Lehrplan-Generator für eine Deutsch-Lern-App (Niveau $level, Schweizer Kontext). Erzeuge den vollständigen Inhalt für ein Szenario.

Szenario: „$title_de" ($title_it)
Beschreibung: $description

Wichtige Kriterien (obbligatorio):
- Nur Wörter/Ausdrücke da uso quotidiano reale, che un $level-Lernender davvero usa in Svizzera. NIENTE vocaboli da manuale, rari o formali.
- „key_phrases": frasi PARLATE, come le diresti a voce ("Sorry, war das zu laut gestern?"), non frasi da libro.

Erzeuge ein JSON-Objekt mit:
- "role_label": il ruolo che l'agente interpreta nel roleplay (es. "Nachbarin", "Arzt").
- "key_phrases": 10 frasi parlate, jeder {de, it, example} (tedesco colloquiale + italiano + esempio breve).
- "vocab": circa 40 Wörter, jeder {de, it, gender, plural, separable, example_de}. "de" include l'articolo (der/die/das) dove applicabile; "gender" è l'articolo o null; "separable" true per i verbi separabili; "example_de" è una frase d'uso breve.
- "imprevisti": 5 imprevisti realistici per Zürich (stringhe brevi in tedesco), legati alla vita quotidiana (es. lavatrice occupata, Kehrichtsack, festa dopo le 22, pacco dal vicino, Velo nel Treppenhaus).
- "swiss_variants": 3 varianti, ognuna {standard, swiss, it} (Hochdeutsch, variante svizzera, italiano).
- "goals": 3–5 obiettivi della conversazione (stringhe in tedesco).

Schweizer Kontext (obbligatorio): Preise in Franken, Grüezi, Säckli statt Tüte, Migros/Coop, Kehricht, Velo, Treppenhaus, Nachtruhe.

Antworte AUSSCHLIESSLICH con un JSON valido (nessun Markdown, nessun testo aggiuntivo).
