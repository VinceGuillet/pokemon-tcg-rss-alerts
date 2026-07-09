# Pokémon TCG RSS Alerts Pro

Surveillance GitHub Actions pour précommandes/restocks Pokémon TCG.

## Installation
1. Crée un repo GitHub, par exemple `pokemon-tcg-rss-alerts`.
2. Uploade tous les fichiers du dossier.
3. Vérifie que le workflow est ici : `.github/workflows/rss.yml`.
4. Onglet **Actions** → **Pokemon TCG RSS Pro** → **Run workflow**.

## GitHub Pages
Settings → Pages → Deploy from a branch → `main` → `/root` → Save.

Flux : `https://TON-PSEUDO.github.io/pokemon-tcg-rss-alerts/pokemon_tcg_alerts.xml`

## Discord
Ajoute un secret GitHub `DISCORD_WEBHOOK_URL` contenant l’URL de ton webhook Discord.

## Telegram
Ajoute `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID` en secrets GitHub.

## Personnalisation
Modifie `config.json` : boutiques, mots-clés positifs, exclusions.

## Fréquence
Configuré toutes les 15 minutes. GitHub peut retarder les runs ; pour les drops en secondes, garde Discord/Telegram de restocks en parallèle.
