import random

def crossover(a, b):
    c = {}
    for key in a.keys():
        c[key] = random.choice([a[key], b[key]])
    return c
