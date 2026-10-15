"""Vérificateur d'infos : un agent Claude qui vérifie une affirmation sur le web.

Exemples :
    python verificateur.py "La Grande Muraille de Chine est visible depuis l'espace"
    python verificateur.py --fichier article.txt
"""

import argparse
import datetime
import re
import sys
import unicodedata
from pathlib import Path
from typing import Callable, Literal

import anthropic
from anthropic import beta_tool

MODEL = "claude-opus-5-5"
DOSSIER_RAPPORTS = Path(__file__).parent / "rapports"

SYSTEM_PROMPT = """Tu es un vérificateur de faits rigoureux et impartial. Tu réponds en français.

Pour chaque affirmation à vérifier :
1. Identifie précisément ce qui est affirmé (et s'il y a plusieurs affirmations, traite-les toutes).
2. Cherche sur le web des sources fiables et indépendantes : institutions officielles, études,
   agences de presse, organismes de fact-checking. Croise au moins deux ou trois sources.
3. Note les points d'accord et de désaccord entre les sources, et la date des informations.
4. Termine TOUJOURS en appelant l'outil `rendre_verdict` avec ta conclusion.

Sois honnête sur l'incertitude : si les preuves sont insuffisantes, dis-le
(verdict "invérifiable") plutôt que de deviner."""

VERDICTS = {
    "vrai": "✅ VRAI",
    "plutot_vrai": "🟢 PLUTÔT VRAI",
    "nuance": "🟡 NUANCÉ",
    "plutot_faux": "🟠 PLUTÔT FAUX",
    "faux": "❌ FAUX",
    "inverifiable": "❔ INVÉRIFIABLE",
}

_client: anthropic.Anthropic | None = None


def client_par_defaut() -> anthropic.Anthropic:
    """Client créé à la première utilisation ; lit ANTHROPIC_API_KEY dans l'environnement."""
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


class Verification:
    """Garde le verdict rendu par l'agent pendant une vérification."""

    def __init__(self) -> None:
        self.verdict: dict | None = None

    def outil(self):
        @beta_tool
        def rendre_verdict(
            verdict: Literal["vrai", "plutot_vrai", "nuance", "plutot_faux", "faux", "inverifiable"],
            confiance: int,
            resume: str,
            explication: str,
            sources: list[str],
        ) -> str:
            """Enregistre le verdict final de la vérification. À appeler une seule fois, à la fin.

            Args:
                verdict: Conclusion sur l'affirmation.
                confiance: Niveau de confiance de 0 à 100.
                resume: Conclusion en une ou deux phrases.
                explication: Raisonnement détaillé en Markdown : ce que disent les sources, nuances, contexte.
                sources: URLs des sources consultées qui appuient la conclusion.
            """
            self.verdict = {
                "verdict": verdict,
                "confiance": max(0, min(100, confiance)),
                "resume": resume,
                "explication": explication,
                "sources": sources,
            }
            return "Verdict enregistré."

        return rendre_verdict


def verifier(
    affirmation: str,
    progression: Callable[[str], None] = print,
    client: anthropic.Anthropic | None = None,
) -> dict | None:
    """Lance l'agent sur une affirmation et renvoie son verdict.

    `progression` reçoit une ligne de texte à chaque recherche ou lecture de page.
    """
    client = client or client_par_defaut()
    verification = Verification()
    tools = [
        {"type": "web_search_20260209", "name": "web_search", "max_uses": 8},
        {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 5},
        verification.outil(),
    ]
    messages = [{"role": "user", "content": f"Vérifie cette affirmation :\n\n{affirmation}"}]

    # Une recherche longue peut mettre le tour en pause ("pause_turn") : le runner
    # s'arrête alors, et on le relance avec l'historique pour reprendre.
    for _ in range(5):
        runner = client.beta.messages.tool_runner(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
            output_config={"effort": "high"},
            # Si le modèle refuse la requête, l'API réessaie avec un modèle de secours.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        dernier = None
        for message in runner:
            dernier = message
            messages.append({"role": "assistant", "content": message.content})
            tool_response = runner.generate_tool_call_response()
            if tool_response is not None:
                messages.append(tool_response)

            for block in message.content:
                if block.type == "server_tool_use" and block.name == "web_search":
                    progression(f"  🔎 recherche : {block.input.get('query', '')}")
                elif block.type == "server_tool_use" and block.name == "web_fetch":
                    progression(f"  📄 lecture : {block.input.get('url', '')}")

            if message.stop_reason == "refusal":
                progression("La requête a été refusée par le modèle.")
                return None

        if dernier is None or dernier.stop_reason != "pause_turn":
            break

    return verification.verdict


def slug(texte: str, longueur: int = 50) -> str:
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", texte).strip("-").lower()[:longueur] or "verification"


def rapport_markdown(affirmation: str, resultat: dict, maintenant: datetime.datetime) -> str:
    """Construit le texte Markdown du rapport."""
    sources = "\n".join(f"- <{url}>" for url in resultat["sources"]) or "_Aucune source._"
    citation = "\n".join(f"> {ligne}" for ligne in affirmation.splitlines())
    return (
        f"# Vérification : {VERDICTS[resultat['verdict']]}\n\n"
        f"{citation}\n\n"
        f"**Confiance :** {resultat['confiance']} %  \n"
        f"**Date :** {maintenant:%d/%m/%Y %H:%M}  \n"
        f"**Modèle :** {MODEL}\n\n"
        f"## En bref\n\n{resultat['resume']}\n\n"
        f"## Analyse\n\n{resultat['explication']}\n\n"
        f"## Sources\n\n{sources}\n\n"
        f"---\n_Rapport généré automatiquement par une IA : vérifiez les sources avant de partager._\n"
    )


def nom_rapport(affirmation: str, maintenant: datetime.datetime) -> str:
    return f"{maintenant:%Y-%m-%d_%H%M}_{slug(affirmation)}.md"


def ecrire_rapport(affirmation: str, resultat: dict) -> Path:
    """Écrit le rapport Markdown dans le dossier rapports/."""
    maintenant = datetime.datetime.now()
    DOSSIER_RAPPORTS.mkdir(exist_ok=True)
    chemin = DOSSIER_RAPPORTS / nom_rapport(affirmation, maintenant)
    chemin.write_text(rapport_markdown(affirmation, resultat, maintenant), encoding="utf-8")
    return chemin


def main() -> int:
    parser = argparse.ArgumentParser(description="Vérifie une affirmation en croisant des sources sur le web.")
    parser.add_argument("affirmation", nargs="?", help="Affirmation à vérifier (entre guillemets).")
    parser.add_argument("--fichier", type=Path, help="Fichier texte contenant l'affirmation ou l'article.")
    args = parser.parse_args()

    if args.fichier:
        affirmation = args.fichier.read_text(encoding="utf-8").strip()
    elif args.affirmation:
        affirmation = args.affirmation
    else:
        affirmation = input("Affirmation à vérifier : ").strip()
    if not affirmation:
        parser.error("aucune affirmation fournie")

    print(f"Vérification en cours de : « {affirmation[:120]} »\n")
    try:
        resultat = verifier(affirmation)
    except anthropic.AuthenticationError:
        print("Clé API invalide ou absente : définissez ANTHROPIC_API_KEY.")
        return 1
    except anthropic.RateLimitError:
        print("Limite de requêtes atteinte, réessayez dans un instant.")
        return 1
    except anthropic.APIStatusError as e:
        print(f"Erreur API {e.status_code} : {e.message}")
        return 1
    except anthropic.APIConnectionError:
        print("Impossible de joindre l'API (connexion réseau ?).")
        return 1

    if resultat is None:
        print("L'agent n'a pas rendu de verdict.")
        return 1

    print(f"\n{VERDICTS[resultat['verdict']]}  (confiance {resultat['confiance']} %)")
    print(resultat["resume"])
    print(f"\nRapport complet : {ecrire_rapport(affirmation, resultat)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
