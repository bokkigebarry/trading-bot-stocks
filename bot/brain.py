"""The self-learning part.

A gradient-boosted classifier is trained on the trade journal: market
conditions at entry -> did the trade make money? Before taking a new
trade, the bot asks the brain for a win probability and skips setups
that resemble past losers.

Until enough trades exist, the brain stays neutral (every candidate
passes) so it can gather experience first.
"""
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier

from .features import FEATURE_NAMES


class Brain:
    def __init__(self, min_trades: int, retrain_every: int,
                 feature_names: list[str] | None = None):
        self.min_trades = min_trades
        self.retrain_every = retrain_every
        self.feature_names = feature_names or FEATURE_NAMES
        self.model: GradientBoostingClassifier | None = None
        self.trained_on = 0  # number of trades the current model saw

    def _to_matrix(self, feature_dicts: list[dict]) -> np.ndarray:
        return np.array(
            [[float(d.get(name, 0.0) or 0.0) for name in self.feature_names]
             for d in feature_dicts]
        )

    def maybe_retrain(self, journal) -> bool:
        """Retrain if enough new trades have accumulated. Returns True if retrained."""
        n = journal.closed_trade_count()
        if n < self.min_trades:
            return False
        if self.model is not None and n - self.trained_on < self.retrain_every:
            return False

        X_dicts, y = journal.training_data()
        if len(set(y)) < 2:  # needs both wins and losses to learn
            return False

        X = self._to_matrix(X_dicts)
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        self.model = GradientBoostingClassifier(
            n_estimators=120, max_depth=3, learning_rate=0.05, subsample=0.8,
            random_state=42,  # reproducible: same journal -> same model
        )
        self.model.fit(X, y)
        self.trained_on = n
        return True

    def win_probability(self, features: dict) -> float:
        """Estimated chance this trade makes money. 0.5 = no opinion yet."""
        if self.model is None:
            return 0.5
        X = self._to_matrix([features])
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        return float(self.model.predict_proba(X)[0, 1])

    def lessons(self) -> list[tuple[str, float]]:
        """Which market conditions matter most, by feature importance."""
        if self.model is None:
            return []
        pairs = list(zip(self.feature_names, self.model.feature_importances_))
        return sorted(pairs, key=lambda p: -p[1])
