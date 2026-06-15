"""
AMRIT RESEARCH OS v4.5
core/dashboard/dashboard.py

Dashboard (Terminal):
  - Live Research Status
  - Knowledge Graph summary
  - Statistics summary
  - Agent Activity
  - Research Memory summary
"""

import datetime


class Dashboard:

    BANNER = """
╔══════════════════════════════════════════════════════════╗
║          🧠  AMRIT RESEARCH OS v4.5  DASHBOARD          ║
╚══════════════════════════════════════════════════════════╝
"""

    def __init__(self):
        self.start_time = datetime.datetime.now()
        self.events = []

    def log_event(self, event: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.events.append(f"[{ts}] {event}")

    def render(
        self,
        memory_summary: dict = None,
        graph_summary: dict = None,
        stats_result: dict = None,
        agent_reviews: dict = None,
        debate_result: dict = None,
    ):
        print(self.BANNER)
        elapsed = datetime.datetime.now() - self.start_time
        print(f"  System Time  : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Uptime       : {str(elapsed).split('.')[0]}")
        print()

        # Research Memory
        print("  ── Research Memory ─────────────────────────────────────")
        if memory_summary:
            print(f"  Total Experiments : {memory_summary.get('total_experiments', 0)}")
            print(f"  Successful        : {memory_summary.get('successful', 0)}")
            print(f"  Failed            : {memory_summary.get('failed', 0)}")
        else:
            print("  No memory data yet.")
        print()

        # Knowledge Graph
        print("  ── Knowledge Graph ──────────────────────────────────────")
        if graph_summary:
            print(f"  Nodes  : {graph_summary.get('nodes', 0)}")
            print(f"  Edges  : {graph_summary.get('edges', 0)}")
            concepts = graph_summary.get("top_concepts", [])[:5]
            print(f"  Top 5  : {', '.join(concepts)}")
        else:
            print("  Graph not built yet.")
        print()

        # Statistics
        print("  ── Statistics ───────────────────────────────────────────")
        if stats_result:
            print(f"  p-value      : {stats_result.get('p_value', 'N/A')}")
            print(f"  effect_size  : {stats_result.get('effect_size', 'N/A')}")
            print(f"  Verdict      : {stats_result.get('verdict', 'N/A')}")
        else:
            print("  No statistics run yet.")
        print()

        # Agent Activity
        print("  ── Agent Activity ───────────────────────────────────────")
        if agent_reviews:
            for agent, review in agent_reviews.items():
                print(f"  [{agent}]")
                print(f"    {review[:80]}...")
        else:
            print("  No agent reviews yet.")
        print()

        # Debate Result
        print("  ── Debate Engine ────────────────────────────────────────")
        if debate_result:
            print(f"  Verdict    : {debate_result.get('judge_verdict', 'N/A')}")
            print(f"  Confidence : {debate_result.get('confidence', 'N/A')}")
        else:
            print("  No debate run yet.")
        print()

        # Event Log
        print("  ── Event Log ────────────────────────────────────────────")
        if self.events:
            for e in self.events[-8:]:
                print(f"  {e}")
        else:
            print("  No events logged.")
        print()
        print("═" * 62)
