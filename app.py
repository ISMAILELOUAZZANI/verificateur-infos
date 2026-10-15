"""Interface web du vérificateur d'infos.

Lancer :  streamlit run app.py
"""

import datetime
import os

import anthropic
import streamlit as st

import verificateur as v

st.set_page_config(page_title="Vérificateur d'infos", page_icon="🔎", layout="centered")

COULEURS = {
    "vrai": st.success,
    "plutot_vrai": st.success,
    "nuance": st.warning,
    "plutot_faux": st.warning,
    "faux": st.error,
    "inverifiable": st.info,
}

EXEMPLES = [
    "La Grande Muraille de Chine est visible à l'œil nu depuis l'espace.",
    "On n'utilise que 10 % de notre cerveau.",
    "Le miel ne se périme jamais.",
]

# --- Barre latérale : clé API ----------------------------------------------
with st.sidebar:
    st.header("⚙️ Réglages")
    cle_env = os.environ.get("ANTHROPIC_API_KEY", "")
    cle = st.text_input(
        "Clé API Anthropic",
        type="password",
        placeholder="déjà définie" if cle_env else "sk-ant-...",
        help="Créez une clé sur platform.claude.com. Elle n'est utilisée que pour cette session.",
    )
    st.caption(f"Modèle : `{v.MODEL}`")
    st.caption("La recherche web est facturée en plus des tokens.")

# --- Page principale --------------------------------------------------------
st.title("🔎 Vérificateur d'infos")
st.write(
    "Collez une affirmation ou un extrait d'article : l'agent cherche sur le web, "
    "croise plusieurs sources et rend un verdict argumenté."
)

if "affirmation" not in st.session_state:
    st.session_state.affirmation = ""

colonnes = st.columns(len(EXEMPLES))
for colonne, exemple in zip(colonnes, EXEMPLES):
    if colonne.button(exemple, use_container_width=True):
        st.session_state.affirmation = exemple

affirmation = st.text_area(
    "Affirmation à vérifier",
    key="affirmation",
    height=140,
    placeholder="Ex. : Le Mont Blanc mesure plus de 5 000 mètres.",
)

if st.button("Vérifier", type="primary", disabled=not affirmation.strip()):
    if not (cle or cle_env):
        st.error("Ajoutez votre clé API dans la barre latérale (à gauche).")
        st.stop()

    client = anthropic.Anthropic(api_key=cle) if cle else None
    resultat = None
    with st.status("Vérification en cours…", expanded=True) as statut:
        try:
            resultat = v.verifier(affirmation.strip(), progression=statut.write, client=client)
        except anthropic.AuthenticationError:
            statut.update(label="Clé API invalide.", state="error")
        except anthropic.RateLimitError:
            statut.update(label="Limite de requêtes atteinte, réessayez dans un instant.", state="error")
        except anthropic.APIStatusError as e:
            statut.update(label=f"Erreur API {e.status_code} : {e.message}", state="error")
        except anthropic.APIConnectionError:
            statut.update(label="Impossible de joindre l'API (connexion réseau ?).", state="error")
        else:
            if resultat is None:
                statut.update(label="L'agent n'a pas rendu de verdict.", state="error")
            else:
                statut.update(label="Vérification terminée", state="complete", expanded=False)

    if resultat:
        maintenant = datetime.datetime.now()
        st.session_state.dernier = {
            "affirmation": affirmation.strip(),
            "resultat": resultat,
            "markdown": v.rapport_markdown(affirmation.strip(), resultat, maintenant),
            "nom": v.nom_rapport(affirmation.strip(), maintenant),
        }

# --- Résultat (reste affiché après un clic sur « Télécharger ») -------------
if dernier := st.session_state.get("dernier"):
    resultat = dernier["resultat"]
    st.divider()
    COULEURS[resultat["verdict"]](f"## {v.VERDICTS[resultat['verdict']]}")
    st.progress(resultat["confiance"] / 100, text=f"Confiance : {resultat['confiance']} %")

    st.subheader("En bref")
    st.write(resultat["resume"])

    with st.expander("Analyse détaillée", expanded=True):
        st.markdown(resultat["explication"])

    st.subheader("Sources")
    if resultat["sources"]:
        for url in resultat["sources"]:
            st.markdown(f"- <{url}>")
    else:
        st.write("Aucune source.")

    st.download_button(
        "⬇️ Télécharger le rapport (Markdown)",
        data=dernier["markdown"],
        file_name=dernier["nom"],
        mime="text/markdown",
    )
    st.caption("Rapport généré par une IA : vérifiez les sources avant de partager.")
