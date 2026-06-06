#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AMRIT RESEARCH OS v3.0
Core Framework
"""

from core.brain import ResearchBrain
from core.memory import MemoryManager
from core.statistics import StatisticalEngine
from core.agents import AgentManager


class AmritResearchOS:

    def __init__(self):

        self.brain = ResearchBrain()
        self.memory = MemoryManager()
        self.stats = StatisticalEngine()
        self.agents = AgentManager()

    def run(self):

        print("🧠 AMRIT RESEARCH OS v3.0")
        print("=" * 50)

        hypothesis = self.brain.generate_hypothesis()

        print(f"\nHypothesis:")
        print(hypothesis)

        result = self.stats.evaluate(hypothesis)

        self.memory.store_result(
            hypothesis,
            result
        )

        review = self.agents.review(
            hypothesis,
            result
        )

        print("\nReview:")
        print(review)


if __name__ == "__main__":
    app = AmritResearchOS()
    app.run()
