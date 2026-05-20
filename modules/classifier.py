"""
Intent Classifier — Naive Bayes (MultinomialNB + TF-IDF).

Classifies natural language database queries into four intents:
SELECT, INSERT, UPDATE, DELETE.
"""

import numpy as np
from sklearn.naive_bayes import MultinomialNB
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score
from sklearn.metrics import classification_report, precision_recall_fscore_support

from data.training_data import TRAINING_DATA


class IntentClassifier:
    def __init__(self):
        self.pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(
                analyzer="word",
                ngram_range=(1, 2),   # unigrams + bigrams
                min_df=1,
                sublinear_tf=True,
                strip_accents="unicode",
                lowercase=True,
            )),
            ("nb", MultinomialNB(alpha=0.5)),
        ])
        self._trained = False
        self.classes_ = None
        self.train()

    # ------------------------------------------------------------------
    def train(self, data=None):
        """Train on provided data or built-in TRAINING_DATA."""
        if data is None:
            data = TRAINING_DATA
        texts, labels = zip(*data)
        self.pipeline.fit(texts, labels)
        self.classes_ = list(self.pipeline.classes_)
        self._trained = True

    # ------------------------------------------------------------------
    def predict(self, text: str) -> str:
        """Return the most probable intent label."""
        return self.pipeline.predict([text])[0]

    def predict_proba(self, text: str) -> dict:
        """Return probability distribution over all classes."""
        probs = self.pipeline.predict_proba([text])[0]
        return dict(zip(self.classes_, probs))

    def predict_with_confidence(self, text: str) -> tuple[str, float]:
        """Return (intent, confidence) where confidence ∈ [0, 1]."""
        proba = self.predict_proba(text)
        intent = max(proba, key=proba.get)
        return intent, round(proba[intent], 4)

    # ------------------------------------------------------------------
    def evaluate(self, test_data: list) -> dict:
        """Compute Precision, Recall, F1 on a test set."""
        texts, true_labels = zip(*test_data)
        pred_labels = [self.predict(t) for t in texts]

        precision, recall, f1, support = precision_recall_fscore_support(
            true_labels, pred_labels, labels=self.classes_, average=None
        )
        macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
            true_labels, pred_labels, average="macro"
        )

        per_class = {
            cls: {
                "precision": round(float(precision[i]), 4),
                "recall": round(float(recall[i]), 4),
                "f1": round(float(f1[i]), 4),
                "support": int(support[i]),
            }
            for i, cls in enumerate(self.classes_)
        }

        return {
            "per_class": per_class,
            "macro": {
                "precision": round(float(macro_p), 4),
                "recall": round(float(macro_r), 4),
                "f1": round(float(macro_f1), 4),
            },
            "predictions": list(zip(texts, true_labels, pred_labels)),
        }

    def cross_validate(self, data=None, cv=5) -> dict:
        """Return mean ± std of cross-validated F1 scores."""
        if data is None:
            data = TRAINING_DATA
        texts, labels = zip(*data)
        scores = cross_val_score(
            self.pipeline, texts, labels, cv=cv, scoring="f1_macro"
        )
        return {
            "cv_scores": scores.tolist(),
            "mean_f1": round(float(scores.mean()), 4),
            "std_f1": round(float(scores.std()), 4),
        }

    # ------------------------------------------------------------------
    def print_report(self, test_data: list):
        texts, true_labels = zip(*test_data)
        pred_labels = [self.predict(t) for t in texts]
        print(classification_report(true_labels, pred_labels, target_names=sorted(set(true_labels))))