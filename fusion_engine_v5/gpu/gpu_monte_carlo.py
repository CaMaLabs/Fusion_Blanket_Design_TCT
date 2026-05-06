import numpy as np
try:
    from numba import cuda
    CUDA_OK = cuda.is_available()
except Exception:
    cuda = None
    CUDA_OK = False

if CUDA_OK:
    @cuda.jit
    def _pfus_kernel(pfus, noise, out):
        i = cuda.grid(1)
        if i < out.size:
            out[i] = pfus * (1.0 + noise[i])

def monte_carlo_plasma(plasma, controller_strength, samples=300000):
    pfus = plasma["pfus_mw"]
    rng = np.random.default_rng()
    noise = rng.normal(0.0, 0.05, size=samples).astype(np.float32)

    if CUDA_OK:
        d_noise = cuda.to_device(noise)
        d_out = cuda.device_array(samples, dtype=np.float32)
        threads = 256
        blocks = (samples + threads - 1) // threads
        _pfus_kernel[blocks, threads](pfus, d_noise, d_out)
        pfus_samples = d_out.copy_to_host()
    else:
        pfus_samples = pfus * (1.0 + noise)

    fail_rate = float((pfus_samples <= 0).mean())
    fail_rate *= (1.0 - 0.75 * controller_strength)
    return {
        "pnet_p50": float(np.median(pfus_samples)),
        "pnet_p05": float(np.quantile(pfus_samples, 0.05)),
        "fail_rate": max(0.0, fail_rate),
    }
