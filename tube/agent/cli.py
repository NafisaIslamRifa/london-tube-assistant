"""Chat with the agent in the terminal.

    python -m tube.agent.cli "Is the Victoria line running?"
    python -m tube.agent.cli            # interactive; 'reset' clears the conversation
"""

from __future__ import annotations

import sys

from tube.agent.agent import TubeAgent


def show(r) -> None:
    print(f"\n{r.answer}\n")
    for t in r.trace:
        flag = " ✗" if t["error"] else ""
        print(f"  🔧 {t['tool']}({', '.join(f'{k}={v!r}' for k, v in t['args'].items())}){flag}")
    if r.guardrails.get("unsupported_urls"):
        print(f"  🛡 unverified links: {r.guardrails['unsupported_urls']}")
    print(f"  ⏱ {r.seconds}s · tokens {r.usage['input_tokens']}/{r.usage['output_tokens']}\n")


def safe_ask(agent: TubeAgent, q: str) -> None:
    try:
        show(agent.ask(q))
    except Exception as exc:  # noqa: BLE001 - show a readable message, not a stack trace
        name = type(exc).__name__
        hint = {"AuthenticationError": "check LLM_API_KEY in .env",
                "NotFoundError": "check LLM_MODEL in .env",
                "RateLimitError": "free-tier limit hit; wait a minute",
                "APIConnectionError": "can't reach the LLM (is LLM_BASE_URL right / Ollama running?)"}
        print(f"\n⚠️  {name}: {hint.get(name, str(exc)[:200])}\n")


def main() -> None:
    agent = TubeAgent()
    if len(sys.argv) > 1:
        safe_ask(agent, " ".join(sys.argv[1:]))
        return
    print("London Tube Assistant. Ask a question ('reset' to start over, Enter to quit).")
    while True:
        try:
            q = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            break
        if q.lower() == "reset":
            agent.reset()
            print("(conversation cleared)")
            continue
        safe_ask(agent, q)


if __name__ == "__main__":
    main()
