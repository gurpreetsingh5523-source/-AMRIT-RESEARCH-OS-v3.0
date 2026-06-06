import random


class StatisticalEngine:

    def evaluate(
        self,
        hypothesis
    ):

        return {
            "p_value":
                round(
                    random.random(),
                    4
                ),

            "effect_size":
                round(
                    random.random(),
                    4
                )
        }
