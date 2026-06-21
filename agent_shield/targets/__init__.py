"""Agent Shield — target adapters.

A *target* is an external system-under-test that Agent Shield drives its attacks
against. Adapters here are optional integrations: each one lazily imports the
target's own code only when invoked, so importing ``agent_shield.targets`` never
pulls a heavyweight dependency and Agent Shield stays independently installable.

Available targets:
  ai_health_journal — the ai-health-journal RAG application, attacked through its
                      real retrieve+generate pipeline (with defence off or on).
"""

__all__: list[str] = ["ai_health_journal"]
