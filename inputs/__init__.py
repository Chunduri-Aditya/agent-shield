"""
Agent Shield — inputs/ module
Direct and indirect prompt injection attacks. L1 adversary level.
"""

from .attacks import ATTACK_BY_ID, ATTACKS, EXFIL_MARKER, Attack

__all__ = ["ATTACKS", "ATTACK_BY_ID", "EXFIL_MARKER", "Attack"]
