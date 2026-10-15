# 🔎 Vérificateur d'infos

Un agent IA qui **vérifie une affirmation ou un article en croisant des sources sur le web**,
puis rend un verdict argumenté avec les liens, dans un rapport Markdown.

Construit avec [Claude](https://www.anthropic.com/claude) (modèle `claude-opus-5-5`) et le SDK Python d'Anthropic.

## Comment ça marche

1. Vous donnez une affirmation (ou un fichier texte contenant un article).
2. L'agent lance des **recherches web**, lit les pages pertinentes et croise plusieurs sources indépendantes.
3. Il rend un **verdict** : ✅ vrai · 🟢 plutôt vrai · 🟡 nuancé · 🟠 plutôt faux · ❌ faux · ❔ invérifiable,
   avec un niveau de confiance.
4. Un **rapport Markdown** est enregistré dans `rapports/` : résumé, analyse détaillée et liste des sources.

## Installation

Python 3.10 ou plus récent est nécessaire.

```bash
git clone https://github.com/ISMAILELOUAZZANI/verificateur-infos.git
cd verificateur-infos
python -m venv .venv
# Windows : .venv\Scripts\activate     macOS/Linux : source .venv/bin/activate
pip install -r requirements.txt
```

Créez une clé API sur [platform.claude.com](https://platform.claude.com), puis :

```bash
# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
# macOS/Linux
export ANTHROPIC_API_KEY="sk-ant-..."
```

> La recherche web doit être activée pour votre organisation dans la console Anthropic.
> Elle est facturée en plus des tokens.

## Utilisation

### 🌐 Interface web

```bash
streamlit run app.py
```

La page s'ouvre dans votre navigateur (http://localhost:8501). Collez une affirmation,
cliquez sur **Vérifier**, suivez les recherches en direct, puis téléchargez le rapport.
Si `ANTHROPIC_API_KEY` n'est pas définie, saisissez votre clé dans la barre latérale.

### 💻 En ligne de commande

```bash
python verificateur.py "La Grande Muraille de Chine est visible à l'œil nu depuis l'espace"
python verificateur.py --fichier article.txt
python verificateur.py          # demande l'affirmation au clavier
```

Exemple de sortie :

```
Vérification en cours de : « La Grande Muraille de Chine est visible à l'œil nu depuis l'espace »

  🔎 recherche : Grande Muraille visible depuis l'espace
  🔎 recherche : Great Wall of China visible from space NASA
  📄 lecture : https://www.nasa.gov/...

❌ FAUX  (confiance 92 %)
Les astronautes confirment que la Grande Muraille n'est pas visible à l'œil nu depuis l'orbite basse...

Rapport complet : rapports/2026-10-16_1430_la-grande-muraille-de-chine-est-visible-a-l-il-nu.md
```

## Structure

| Fichier | Rôle |
|---|---|
| `verificateur.py` | L'agent : boucle d'outils, recherche web, verdict, rapport |
| `app.py` | Interface web (Streamlit) |
| `requirements.txt` | Dépendances Python |
| `rapports/` | Rapports générés (ignorés par git) |

## Limites

- L'IA peut se tromper : **vérifiez toujours les sources** avant de partager un verdict.
- La qualité dépend de ce qui est trouvable en ligne ; les événements très récents peuvent être mal couverts.

## Licence

MIT
