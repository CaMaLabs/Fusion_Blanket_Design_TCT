# Fusion Engine v5

Unified reactor optimizer with:
- Plasma core model
- Continuous TCT / plasmoid control
- GPU Monte Carlo robustness
- ELM damage model
- Lithium wall thermals
- MHD drag + pumping power
- Plant power balance
- Engineering penalties
- Integrated blanket genome
- Material learning
- OpenMC finalist validation

## Settings
- Population size: 64
- Generations: 30
- Top 5 validated each generation
- OpenMC batches: 80
- OpenMC particles: 300000

## Run
```bash
pip install -r requirements.txt
python run_reactor_optimizer.py
```

## Notes
- Every design includes plasma + blanket + TCT + wall + plant variables.
- Top 5 each generation go through explicit-layer OpenMC validation.
- The rest use the fast surrogate to keep runtime manageable.
