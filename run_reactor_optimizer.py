import json
import multiprocessing
multiprocessing.set_start_method("spawn", force=True)

from fusion_engine_v5.optimizer.reactor_optimizer import optimize

if __name__ == "__main__":
    optimize()
