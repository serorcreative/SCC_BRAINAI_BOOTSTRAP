"""**brainai_app** — couche application / composition de BrainAI (façade produit).

Vit **hors** du package moteur ``scc_brainai_bootstrap`` (donc **hors** du périmètre scanné par la frontière
S9). Cette couche a le droit de **construire** BrainAI, d'**injecter** ses capacités, de bâtir Stores /
RunContext / Workspace, d'appeler **exclusivement** ``BrainAI.pursue(...)`` et de **projeter** l'``Outcome``
vers un ViewModel de transport. Elle ne contient **aucune** logique métier, cognitive, décisionnelle ou de
gouvernance : elle **câble, transporte et reflète**.
"""
