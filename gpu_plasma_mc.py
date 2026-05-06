import numpy as np
from numba import cuda


@cuda.jit
def plasma_mc_kernel(pfus, noise, results):

    i = cuda.grid(1)

    if i < results.size:

        perturb = 1.0 + noise[i]

        results[i] = pfus * perturb


def plasma_mc(pfus, samples=10000):

    noise = np.random.normal(0, 0.05, samples)

    d_noise = cuda.to_device(noise)
    d_results = cuda.device_array(samples)

    threads = 256
    blocks = (samples + threads - 1) // threads

    plasma_mc_kernel[blocks, threads](pfus, d_noise, d_results)

    return d_results.copy_to_host()
