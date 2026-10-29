"""Avaliação de licenças de materiais visuais. Regra: direitos desconhecidos = rejeitado."""
from __future__ import annotations

import re

STOCK_LICENSES = {
    "pexels": ("Pexels License", "https://www.pexels.com/license/",
               "Uso comercial e edição permitidos, sem atribuição obrigatória; não vender o material sem alterações, "
               "não sugerir endosso de pessoas/marcas identificáveis."),
    "pixabay": ("Pixabay Content License", "https://pixabay.com/service/license-summary/",
                "Uso comercial e edição permitidos, sem atribuição obrigatória; não redistribuir como banco de imagens, "
                "não sugerir endosso de pessoas/marcas identificáveis."),
}


def evaluate(license_name: str | None, restrictions: str = "", usage_terms: str = "") -> dict:
    """Retorna status (aceita/condicional/rejeitada), necessidade de atribuição, share-alike e nota."""
    name = (license_name or "").strip()
    low = f"{name} {usage_terms}".lower()
    if not name:
        return {"status": "rejeitada", "attribution": True, "share_alike": False, "note": "Licença desconhecida."}
    if re.search(r"\bnc\b|non-?commercial|não comercial", low):
        return {"status": "rejeitada", "attribution": True, "share_alike": False, "note": "Licença não permite uso comercial (NC)."}
    if re.search(r"\bnd\b|no ?deriv", low):
        return {"status": "rejeitada", "attribution": True, "share_alike": False, "note": "Licença não permite edição (ND)."}
    status, note = "aceita", ""
    if restrictions.strip():
        status, note = "condicional", f"Restrições declaradas: {restrictions.strip()[:160]}."
    if "cc0" in low or "public domain" in low or "domínio público" in low or low.startswith("pd"):
        return {"status": status, "attribution": False, "share_alike": False,
                "note": (note + " Domínio público/CC0: crédito recomendado, não obrigatório.").strip()}
    if re.search(r"cc[ -]by[ -]sa", low):
        return {"status": "condicional", "attribution": True, "share_alike": True,
                "note": (note + " CC BY-SA: exige atribuição e compartilhamento pela mesma licença; avaliar se o vídeo "
                         "final pode ser licenciado assim antes de publicar.").strip()}
    if re.search(r"cc[ -]by\b", low):
        return {"status": status, "attribution": True, "share_alike": False,
                "note": (note + " CC BY: permitido com atribuição (gerada automaticamente).").strip()}
    if name in ("Pexels License", "Pixabay Content License"):
        return {"status": status, "attribution": False, "share_alike": False, "note": note}
    return {"status": "rejeitada", "attribution": True, "share_alike": False, "note": f"Licença '{name}' não reconhecida: revisar manualmente."}


def credit_line(title: str, author: str, provider: str, license_name: str, page_url: str) -> str:
    return f"“{title}” — {author} — {provider} — {license_name} — {page_url}"
