from collections import defaultdict

class MaterialLearner:
    def __init__(self, candidates):
        self.weights = {c: 1 for c in candidates}

    def update(self, rows):
        counts = defaultdict(int)
        for r in rows:
            for key in ("l1", "l2", "l3", "l4"):
                counts[r["design"][key]] += 1
        for m in self.weights:
            self.weights[m] = 1 + counts[m]
