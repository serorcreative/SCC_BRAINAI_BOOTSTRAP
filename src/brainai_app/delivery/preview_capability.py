"""Capacité **preview** — surface substituable (JALON 2, Q4=A / T6).

Décision propriétaire Q4 = **preview locale RÉELLE** : l'artefact bâti est réellement servi (loopback + jeton +
default-deny). Mais la preview reste **architecturalement une CAPACITÉ** enregistrée/résolue via le registre :
aucun câblage métier ne doit empêcher de remplacer ultérieurement ``preview.local`` (``LOCAL_PREVIEW``) par
``deploy.public`` (``DEPLOY_PUBLIC``) — **le déploiement public est différé RS-2/J3+**, jamais réalisé en J2.

Le contrat est **minimal et agnostique** au fournisseur : ``open(workspace, *, entrypoint) → handle`` où le
handle expose ``url_for``/``preview_ref``/``close``. La logique métier (livraison, vérification) dépend de ce
**Protocol**, jamais d'une implémentation concrète — d'où la substituabilité inconditionnelle (I9)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from scc_brainai_bootstrap.builder.workspace import Workspace
from brainai_app.delivery.serving import WorkspacePreview


@runtime_checkable
class PreviewCapability(Protocol):
    """**Capacité** « servir/livrer un artefact bâti » (R8). ``local`` aujourd'hui, ``public`` demain — même
    contrat, implémentation substituée par descriptor/binder."""

    capability: str
    name: str

    def open(self, workspace: Workspace, *, entrypoint: str = "index.html") -> Any:
        ...


class LocalPreviewAdapter:
    """Implémentation **preview locale** (loopback confiné) de :class:`PreviewCapability`. Substituable : un
    ``deploy.public`` fournirait la même surface (``url_for``/``preview_ref``) sans toucher la logique métier."""

    capability = "preview.local"
    name = "local_loopback"

    def open(self, workspace: Workspace, *, entrypoint: str = "index.html") -> WorkspacePreview:
        """Ouvre une preview locale **vivante** (serveur loopback démarré). L'appelant ferme le handle (``close``)."""
        return WorkspacePreview(workspace, entrypoint=entrypoint).start()

    def contract(self):
        """Contrat d'adaptateur complet (T2) — capacité **locale** : aucun appel fournisseur, aucun canal d'auth
        externe, coût ``unavailable``, confinement loopback + jeton + default-deny + ``resolve_within``."""
        from scc_brainai_bootstrap.builder.adapter_contract import local_surface_contract
        return local_surface_contract(capability=self.capability)


__all__ = ["PreviewCapability", "LocalPreviewAdapter"]
