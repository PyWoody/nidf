import curio
from .nidf import main

def run():
    with curio.Kernel() as kernel:
        try:
            kernel.run(main, shutdown=True)
        except (KeyboardInterrupt, Exception):
            return

run()
