# AliDonerBot — Plan de features

Idées à implémenter, classées par effort / impact.

---

## 🟢 Facile et utile

| Feature | Description |
|--------|-------------|
| **`/last`** | Renvoyer le dernier recap à la demande (pour ceux qui l'ont raté ou veulent le relire). |
| **`/sources`** | Afficher la liste des sources utilisées (transparence). |
| **Thèmes personnalisés** | `/focus coding` ou `/focus business` — chaque abonné choisit ses catégories et reçoit un recap filtré. |
| **Heure personnalisée** | `/heure 7:30` — choisir à quelle heure recevoir le recap (certains préfèrent le soir). |

---

## 🟡 Moyen effort, gros impact

| Feature | Description |
|--------|-------------|
| **Score de confiance** | Indicateur par news : 1 source vs 5 sources = pas le même poids. Afficher un indicateur de fiabilité. |
| **Résumé hebdo le dimanche** | `/week` ou envoi auto le dimanche : les 5 news les plus marquantes de la semaine. |
| **Trending alert** | Si une news explose en milieu de journée (modèle qui sort, grosse levée), envoi d’une alerte immédiate au lieu d’attendre le lendemain. |
| **Mode quiz** | Chaque soir, petit quiz basé sur les news du matin (« Combien a levé Anthropic ? »). Gamification + rétention. |
| **Feedback** | Après chaque recap : « Ce recap était 🔥 ou 💤 ? » pour améliorer la sélection. |

---

## 🔴 Plus ambitieux

| Feature | Description |
|--------|-------------|
| **Dashboard web** | Page simple (Vercel/Netlify gratuit) : historique des recaps, recherche, stats. |
| **Multi-langue** | `/lang en` pour recevoir le recap en anglais. Élargit la base. |
| **Podcast audio** | LLM génère un script, TTS gratuit (ex. ElevenLabs free tier) le lit, le bot envoie un vocal de 2 min. Pour ceux qui préfèrent écouter en marchant. |
| **Monétisation** | Version gratuite = 5 news. Version payante (2€/mois via Stripe) = 10 news + concept du jour + idée à piquer. Licence déjà prête. |
| **Canal Telegram public** | Au lieu du bot 1-to-1, un canal `@AliDonerIA` où tu publies le recap. Plus viral, les gens partagent le lien du canal. |

---

*Dernière mise à jour : 2026-02*
