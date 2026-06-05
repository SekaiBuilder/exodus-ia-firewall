"""L3 — Policy engine. Decides, configurably, what happens to each detection.

The decision chain is:   kind  ->  sensitivity tier  ->  action

Defaults are fail-closed: an unknown kind is treated as SECRET, and an unknown
tier maps to BLOCK. The user owns all of this via a YAML file (policy.example.yaml).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import yaml

from exodus.classify.sensitivity import Sensitivity


class Action(str, Enum):
    FORWARD = "forward"            # leave as-is (not sensitive enough to touch)
    PSEUDONYMIZE = "pseudonymize"  # reversible placeholder (restored on the way back)
    BLOCK = "block"                # non-reversible redaction (value never comes back)
    # ABSTRACT / LOCAL actions arrive in M4 (they need the local model).


# Defaults: every known secret is SECRET; PII starts as PUBLIC (off) until you opt in.
_DEFAULT_KIND_TIERS: dict[str, Sensitivity] = {
    # --- Secrets: never safe to leak (pseudonymized; restored on the way back) ---
    "anthropic_key": Sensitivity.SECRET,
    "openai_key": Sensitivity.SECRET,
    "openai_project_key": Sensitivity.SECRET,
    "aws_access_key": Sensitivity.SECRET,
    "google_api_key": Sensitivity.SECRET,
    "google_oauth_token": Sensitivity.SECRET,
    "github_token": Sensitivity.SECRET,
    "github_oauth": Sensitivity.SECRET,
    "github_pat": Sensitivity.SECRET,
    "slack_token": Sensitivity.SECRET,
    "slack_webhook": Sensitivity.SECRET,
    "stripe_key": Sensitivity.SECRET,
    "sendgrid_key": Sensitivity.SECRET,
    "npm_token": Sensitivity.SECRET,
    "jwt": Sensitivity.SECRET,
    "private_key_block": Sensitivity.SECRET,
    "generic_bearer": Sensitivity.SECRET,
    "db_uri_credentials": Sensitivity.SECRET,
    # --- Financial / identity PII: sensitive by default → HIGH (pseudonymize) ---
    "credit_card": Sensitivity.HIGH,
    "iban": Sensitivity.HIGH,
    "es_dni": Sensitivity.HIGH,
    "es_nie": Sensitivity.HIGH,
    "us_ssn": Sensitivity.HIGH,
    # --- Lower-sensitivity PII: detected but forwarded until you opt in ---
    "email": Sensitivity.PUBLIC,
    "ipv4": Sensitivity.PUBLIC,
    "phone_intl": Sensitivity.PUBLIC,
}
_DEFAULT_TIER_ACTIONS: dict[Sensitivity, Action] = {
    Sensitivity.PUBLIC: Action.FORWARD,
    Sensitivity.LOW: Action.PSEUDONYMIZE,
    Sensitivity.MEDIUM: Action.PSEUDONYMIZE,  # becomes ABSTRACT in M4
    Sensitivity.HIGH: Action.PSEUDONYMIZE,    # becomes LOCAL in M4
    Sensitivity.SECRET: Action.PSEUDONYMIZE,
}


@dataclass
class Policy:
    kind_tiers: dict[str, Sensitivity] = field(default_factory=lambda: dict(_DEFAULT_KIND_TIERS))
    tier_actions: dict[Sensitivity, Action] = field(default_factory=lambda: dict(_DEFAULT_TIER_ACTIONS))

    def action_for_kind(self, kind: str) -> Action:
        tier = self.kind_tiers.get(kind, Sensitivity.SECRET)   # unknown kind -> SECRET (fail-closed)
        return self.tier_actions.get(tier, Action.BLOCK)       # unknown tier -> BLOCK (fail-closed)

    @classmethod
    def default(cls) -> "Policy":
        return cls()

    @classmethod
    def from_yaml(cls, path: str) -> "Policy":
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        kind_tiers = dict(_DEFAULT_KIND_TIERS)
        for kind, tier_name in (data.get("kinds") or {}).items():
            kind_tiers[kind] = Sensitivity[str(tier_name).upper()]
        tier_actions = dict(_DEFAULT_TIER_ACTIONS)
        for tier_name, action_name in (data.get("tiers") or {}).items():
            tier_actions[Sensitivity[str(tier_name).upper()]] = Action(str(action_name).lower())
        return cls(kind_tiers=kind_tiers, tier_actions=tier_actions)
