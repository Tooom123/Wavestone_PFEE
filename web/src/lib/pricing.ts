// Tarifs utilises pour situer le cout d'un run local. Chaque valeur a une source et une date :
// les modifier ici, nulle part ailleurs.

/** Electricite : Tarif Bleu Pro, € HT/kWh, au 1er aout 2026 (Selectra). */
export const ELECTRICITY_EUR_PER_KWH = 0.1624;

/** API Claude, $ par million de tokens (platform.claude.com/docs/en/about-claude/pricing, 05/11/2026). */
export const API_PRICES_USD_PER_MTOK = [
  { model: "Claude Haiku 5.5", input: 0.1, output: 0.5 },
  { model: "Claude Sonnet 5.5", input: 2, output: 10 },
  { model: "Claude Opus 5.5", input: 4, output: 20 },
] as const;
