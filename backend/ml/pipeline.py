"""Full ML pipeline:  .venv\\Scripts\\python -m backend.ml.pipeline

1. preprocess  - point-in-time training table (raw ratings)
2. debias      - offline fairness audit writes bias-corrected ratings
3. preprocess  - rebuild so the past-rating feature uses corrected ratings
4. train       - compare variants, calibrate, evaluate, save production model
"""
from . import debias, preprocess, train
from ..db import conn


def run():
    with conn() as c:
        c.execute("TRUNCATE rating_adjustments")
    for step in (preprocess.main, debias.main, preprocess.main, train.main):
        print(f"\n===== {step.__module__}.{step.__name__} =====")
        step()


if __name__ == "__main__":
    run()
