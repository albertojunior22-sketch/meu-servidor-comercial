"""
restricoes_ramo.py
==================
Restrições de distribuição por ramo — bloco completamente independente.

Quando restricoes=None em distribuir() o comportamento é 100% idêntico ao atual.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RestricoesRamo:
    """
    Restrições de distribuição para um ramo específico.

    corte_somente_bf: bool
        True → todo o corte deste ramo vai obrigatoriamente para BF.
        Não pode ser usado em CA/CF de nenhum outro ramo.

    aterro_aceita_c1/c2/c3: bool
        Define quais categorias de corte o aterro deste ramo aceita.
        Se todas False → sem restrição (comportamento padrão).

    aterro_usa_ae: bool
        True → o aterro deste ramo pode ser suprido por AE.

    ae_label: str
        Label do AE a usar (ex: 'AE-1'). Vazio = qualquer AE disponível.
    """
    ramo:              str
    corte_somente_bf:  bool = False
    aterro_aceita_c1:  bool = True
    aterro_aceita_c2:  bool = True
    aterro_aceita_c3:  bool = True
    aterro_usa_ae:     bool = False
    ae_label:          str  = ""
    prioridade_c3_c2_c1: bool = False  # True → na rodada externa esgota C3 antes de C2 e C1

    def aterro_sem_restricao(self) -> bool:
        """True se nenhuma restrição de aterro foi configurada."""
        return (self.aterro_aceita_c1 and self.aterro_aceita_c2 and
                self.aterro_aceita_c3 and not self.aterro_usa_ae)


@dataclass
class ConfigRestricoes:
    """Container de todas as restrições por ramo."""
    restricoes: List[RestricoesRamo] = field(default_factory=list)

    def get(self, ramo: str) -> Optional[RestricoesRamo]:
        """Retorna as restrições do ramo ou None se não configurado."""
        for r in self.restricoes:
            if r.ramo == ramo:
                return r
        return None

    def tem_restricoes(self) -> bool:
        """True se há pelo menos uma restrição configurada."""
        return bool(self.restricoes)

    def corte_somente_bf(self, ramo: str) -> bool:
        """True se o corte deste ramo vai obrigatoriamente para BF."""
        r = self.get(ramo)
        return r.corte_somente_bf if r else False

    def aterro_aceita(self, ramo: str, categoria: str) -> bool:
        """
        True se o aterro deste ramo aceita a categoria de corte informada.
        Sem restrição configurada → aceita tudo.
        """
        r = self.get(ramo)
        if r is None:
            return True
        if r.aterro_sem_restricao():
            return True
        if categoria == 'C1':
            return r.aterro_aceita_c1
        if categoria == 'C2':
            return r.aterro_aceita_c2
        if categoria == 'C3':
            return r.aterro_aceita_c3
        return True  # CA, CF, CL — sem restrição

    def aterro_usa_ae(self, ramo: str) -> bool:
        """True se o aterro deste ramo pode usar AE."""
        r = self.get(ramo)
        return r.aterro_usa_ae if r else False

    def ae_label(self, ramo: str) -> str:
        """Label do AE preferido para este ramo. Vazio = qualquer."""
        r = self.get(ramo)
        return r.ae_label if r else ""


def restricoes_to_dict(cfg: ConfigRestricoes) -> dict:
    return {
        "restricoes": [
            {
                "ramo":                r.ramo,
                "corte_somente_bf":    r.corte_somente_bf,
                "aterro_aceita_c1":    r.aterro_aceita_c1,
                "aterro_aceita_c2":    r.aterro_aceita_c2,
                "aterro_aceita_c3":    r.aterro_aceita_c3,
                "aterro_usa_ae":       r.aterro_usa_ae,
                "ae_label":            r.ae_label,
                "prioridade_c3_c2_c1": r.prioridade_c3_c2_c1,
            }
            for r in cfg.restricoes
        ]
    }


def dict_to_restricoes(d: dict) -> ConfigRestricoes:
    cfg = ConfigRestricoes()
    for r in d.get("restricoes", []):
        cfg.restricoes.append(RestricoesRamo(
            ramo                = r.get("ramo", ""),
            corte_somente_bf    = r.get("corte_somente_bf", False),
            aterro_aceita_c1    = r.get("aterro_aceita_c1", True),
            aterro_aceita_c2    = r.get("aterro_aceita_c2", True),
            aterro_aceita_c3    = r.get("aterro_aceita_c3", True),
            aterro_usa_ae       = r.get("aterro_usa_ae", False),
            ae_label            = r.get("ae_label", ""),
            prioridade_c3_c2_c1 = r.get("prioridade_c3_c2_c1", False),
        ))
    return cfg