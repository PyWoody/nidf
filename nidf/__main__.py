import curio
from .nidf import main

with curio.Kernel() as kernel:
    kernel.run(main, shutdown=True)
