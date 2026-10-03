# Historical DAX membership pilot

Use the same frozen ranked-equity and futures experiment with the full 40-member DAX universe over 10 March–27 July 2025. The membership CSV records verified coverage bounds, not each company's original admission date. STOXX historical changes show the preceding change on 27 December 2024 (Covestro out, Fresenius Medical Care in) and the next change on 22 September 2025 (Sartorius and Porsche AG out; GEA and Scout24 in). No change falls inside the pilot.

Source: https://www.stoxx.com/documents/stoxxnet/Documents/Indices/Common/Indexguide/Historical_Index_Compositions.pdf, DAX section, printed pages 3–5. June review confirmation: https://stoxx.com/stoxx-gibt-neuzusammensetzung-der-dax-blue-chip-indizes-bekannt-4-june-2025/. Original captured source bodies reside in context `sources/dax-membership-2025/`. Yahoo tickers map to the German ordinary/preference share classes represented in DAX.

Reject an uncovered membership date or missing equity rather than silently shrink the universe. Rankings use prior-session closes and the documented pilot costs and chronological development split. The economic hypothesis and finite grid are unchanged; this is a universe correction, not fresh validation. Adjusted Yahoo prices remain retrospective. Final holdout stays locked. Separate batch and data directories preserve the 30-stock experiment.
