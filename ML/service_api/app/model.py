import json
import lightgbm as lgb
import numpy as np
from pathlib import Path
from typing import Dict, Any


class ServiceModel:
    def __init__(self, model_path: Path, meta_path: Path):
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")
        if not meta_path.exists():
            raise FileNotFoundError(f"Meta file not found: {meta_path}")

        self.model = lgb.Booster(model_file=str(model_path))
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self.features = meta["features"]
        self.threshold = float(meta["threshold"])

    def predict_proba(self, row: Dict[str, Any]) -> float:
        x = np.array([row.get(f, 0) for f in self.features], dtype=float).reshape(1, -1)
        prob = float(self.model.predict(x)[0])
        return prob
