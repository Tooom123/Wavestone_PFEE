# Image d'execution du code genere par le LLM.
# Volontairement minimale : uniquement les bibliotheques d'analyse, aucun outil reseau.
FROM python:3.15-slim

# Dependances d'analyse. Versions epinglees pour que deux runs restent comparables.
RUN pip install --no-cache-dir \
        pandas==2.2.3 \
        numpy==2.1.3 \
        scipy==1.14.1 \
        scikit-learn==1.5.2 \
        plotly==5.24.1 \
        duckdb==1.1.3 \
    && rm -rf /root/.cache

# Utilisateur non privilegie : le code genere ne tourne jamais en root.
RUN useradd --create-home --uid 10001 sandbox
USER sandbox

# Rend l'encodeur JSON tolerant aux types numpy, que le code genere manipule sans y penser.
COPY sitecustomize.py /usr/local/lib/python3.12/site-packages/sitecustomize.py
# Helpers d'ecriture des artefacts : `from agent_out import save_table, ...`
COPY agent_out.py /usr/local/lib/python3.12/site-packages/agent_out.py

WORKDIR /workspace

# /workspace/data  : CSV montes en lecture seule
# /workspace/out   : seule zone accessible en ecriture
CMD ["python", "/workspace/code.py"]
