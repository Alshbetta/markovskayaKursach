"""
Metrics Visualizer.

Generates 8 plots:
  1. classification_metrics.png  — Precision / Recall / F1 bar chart per class
  2. confusion_matrix.png        — Seaborn heatmap
  3. security_distribution.png   — Pie chart of audit verdicts
  4. cv_scores.png               — Cross-validation F1 distribution (5-fold)
  5. top_features.png            — Top-5 TF-IDF keywords per class (2×2 grid)
  6. class_priors.png            — Prior probabilities P(class): pie + bar
  7. baseline_comparison.png     — Naive Bayes vs baseline methods
  8. query_log_scores.png        — Log-probability scores for an example query
"""

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")   # non-interactive backend; must be set before pyplot import
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

import config

# seaborn 0.13+ renamed style strings — apply theme safely
try:
    sns.set_theme(style="darkgrid", palette="muted")
except Exception:
    pass

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.unicode_minus": False,
})

# Consistent color palette
_PALETTE = {
    "precision": "#2196F3",
    "recall":    "#4CAF50",
    "f1":        "#FF9800",
    "safe":      "#4CAF50",
    "regex":     "#F44336",
    "llm":       "#FF9800",
}

# Per-class colors (alphabetical order: DELETE, INSERT, SELECT, UPDATE)
_CLASS_COLORS = {
    "DELETE": "#F44336",
    "INSERT": "#4CAF50",
    "SELECT": "#2196F3",
    "UPDATE": "#FF9800",
}


class MetricsVisualizer:
    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or config.PLOTS_DIR
        os.makedirs(self.output_dir, exist_ok=True)

    def _savefig(self, name: str) -> str:
        path = os.path.join(self.output_dir, name)
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()
        return path

    # ── 1. Precision / Recall / F1 per class ────────────────────────────────

    def plot_classification_metrics(
        self, y_true: list, y_pred: list, labels: list
    ) -> str:
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_true, y_pred, labels=labels, average=None, zero_division=0
        )

        x = np.arange(len(labels))
        w = 0.25

        fig, ax = plt.subplots(figsize=(11, 6))
        b1 = ax.bar(x - w, precision, w, label="Precision", color=_PALETTE["precision"], alpha=0.87)
        b2 = ax.bar(x,     recall,    w, label="Recall",    color=_PALETTE["recall"],    alpha=0.87)
        b3 = ax.bar(x + w, f1,        w, label="F1-Score",  color=_PALETTE["f1"],        alpha=0.87)

        ax.set_xlabel("Класс (интент)", fontsize=12)
        ax.set_ylabel("Значение метрики", fontsize=12)
        ax.set_title(
            "График 1: Метрики классификатора намерений (Naive Bayes)\n"
            "Precision, Recall, F1-Score по классам",
            fontsize=13, fontweight="bold",
        )
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=11)
        ax.set_ylim(0, 1.18)
        ax.legend(fontsize=11)
        ax.grid(axis="y", alpha=0.4)

        for bars in (b1, b2, b3):
            for bar in bars:
                h = bar.get_height()
                ax.annotate(
                    f"{h:.2f}",
                    xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8.5,
                )

        plt.tight_layout()
        return self._savefig("classification_metrics.png")

    # ── 2. Confusion matrix ──────────────────────────────────────────────────

    def plot_confusion_matrix(
        self, y_true: list, y_pred: list, labels: list
    ) -> str:
        cm = confusion_matrix(y_true, y_pred, labels=labels)

        fig, ax = plt.subplots(figsize=(7, 6))
        sns.heatmap(
            cm, annot=True, fmt="d", cmap="Blues",
            xticklabels=labels, yticklabels=labels,
            linewidths=0.5, ax=ax,
        )
        ax.set_xlabel("Предсказанный класс", fontsize=12)
        ax.set_ylabel("Истинный класс", fontsize=12)
        ax.set_title(
            "График 2: Матрица ошибок классификатора\n(Confusion Matrix)",
            fontsize=13, fontweight="bold",
        )
        plt.tight_layout()
        return self._savefig("confusion_matrix.png")

    # ── 3. Security audit distribution ──────────────────────────────────────

    def plot_security_distribution(self, audit_results: list) -> str:
        safe      = sum(1 for r in audit_results if not r.get("blocked"))
        blk_regex = sum(1 for r in audit_results if r.get("final_verdict") == "BLOCKED_REGEX")
        blk_llm   = sum(1 for r in audit_results if r.get("final_verdict") == "BLOCKED_LLM")

        labels = ["Безопасно", "Заблокировано\n(Regex)", "Заблокировано\n(LLM)"]
        values = [safe, blk_regex, blk_llm]
        colors = [_PALETTE["safe"], _PALETTE["regex"], _PALETTE["llm"]]

        filtered = [(l, v, c) for l, v, c in zip(labels, values, colors) if v > 0]
        if not filtered:
            filtered = [("Нет данных", 1, "#BDBDBD")]
        labels_f, values_f, colors_f = zip(*filtered)

        fig, ax = plt.subplots(figsize=(8, 6))
        ax.pie(
            values_f, labels=labels_f, colors=colors_f,
            autopct="%1.1f%%", explode=[0.04] * len(values_f),
            startangle=90, textprops={"fontsize": 11},
        )
        ax.set_title(
            "График 3: Распределение результатов аудита безопасности\nSQL-запросов",
            fontsize=13, fontweight="bold",
        )
        plt.tight_layout()
        return self._savefig("security_distribution.png")

    # ── 4. Cross-validation F1 scores ───────────────────────────────────────

    def plot_cv_scores(self, cv_scores: list) -> str:
        fig, ax = plt.subplots(figsize=(9, 5))
        folds = list(range(1, len(cv_scores) + 1))
        ax.bar(folds, cv_scores, color=_PALETTE["f1"], alpha=0.85, edgecolor="white")
        mean_val = float(np.mean(cv_scores))
        ax.axhline(mean_val, color="#333", linestyle="--", linewidth=1.8,
                   label=f"Среднее = {mean_val:.4f}")
        ax.set_xlabel("Fold (блок)", fontsize=12)
        ax.set_ylabel("Macro F1-Score", fontsize=12)
        ax.set_title(
            "График 4: Кросс-валидация классификатора (5-fold CV)",
            fontsize=13, fontweight="bold",
        )
        ax.set_ylim(0, 1.1)
        ax.set_xticks(folds)
        ax.legend(fontsize=11)
        ax.grid(axis="y", alpha=0.4)
        for i, v in zip(folds, cv_scores):
            ax.text(i, v + 0.01, f"{v:.3f}", ha="center", va="bottom", fontsize=9)
        plt.tight_layout()
        return self._savefig("cv_scores.png")

    # ── 5. Top TF-IDF features per class (2×2 grid) ─────────────────────────

    def plot_top_features(self, classifier, top_n: int = 5) -> str:
        """
        Horizontal bar charts showing the top-N most weighted unigrams per class.
        Uses MultinomialNB.feature_count_ (raw occurrence counts).
        """
        pipeline  = classifier.pipeline
        tfidf     = pipeline.named_steps["tfidf"]
        nb        = pipeline.named_steps["nb"]

        try:
            feature_names = tfidf.get_feature_names_out()
        except AttributeError:           # sklearn < 1.0
            feature_names = np.array(tfidf.get_feature_names())

        classes = nb.classes_
        counts  = nb.feature_count_     # shape: (n_classes, n_features)

        fig, axes = plt.subplots(2, 2, figsize=(14, 9))
        fig.suptitle(
            "График 5: Топ-5 ключевых слов по классам\n(частота в обучающей выборке)",
            fontsize=14, fontweight="bold",
        )

        for ax, cls in zip(axes.flatten(), classes):
            idx      = list(classes).index(cls)
            top_idx  = counts[idx].argsort()[-top_n:]          # indices of top-N features
            top_feat = feature_names[top_idx][::-1]            # most-important first
            top_vals = counts[idx][top_idx][::-1]
            color    = _CLASS_COLORS.get(cls, "#90A4AE")

            bars = ax.barh(top_feat, top_vals, color=color, alpha=0.85)
            ax.set_title(cls, fontsize=13, fontweight="bold", color=color)
            ax.set_xlabel("Частота", fontsize=10)
            ax.invert_yaxis()
            ax.grid(axis="x", alpha=0.3)

            for bar, val in zip(bars, top_vals):
                ax.text(
                    bar.get_width() + 0.15, bar.get_y() + bar.get_height() / 2,
                    f"{int(val)}", va="center", fontsize=9, fontweight="bold",
                )

        plt.tight_layout()
        return self._savefig("top_features.png")

    # ── 6. Prior probabilities P(class) ─────────────────────────────────────

    def plot_class_priors(self, classifier) -> str:
        nb      = classifier.pipeline.named_steps["nb"]
        classes = nb.classes_
        priors  = np.exp(nb.class_log_prior_)    # convert log → probability
        colors  = [_CLASS_COLORS.get(c, "#90A4AE") for c in classes]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 6))
        fig.suptitle(
            "График 6: Априорные вероятности P(класс)",
            fontsize=14, fontweight="bold",
        )

        # Pie chart
        ax1.pie(
            priors, labels=classes, colors=colors,
            autopct="%1.1f%%", startangle=90,
            textprops={"fontsize": 11},
        )
        ax1.set_title("Доля каждого класса", fontsize=11)

        # Bar chart
        bars = ax2.bar(classes, priors, color=colors, alpha=0.87, edgecolor="white")
        ax2.set_xlabel("Класс (интент)", fontsize=11)
        ax2.set_ylabel("Вероятность", fontsize=11)
        ax2.set_title("P(класс) — числовые значения", fontsize=11)
        ax2.set_ylim(0, max(priors) * 1.30)
        ax2.grid(axis="y", alpha=0.4)

        for bar, val in zip(bars, priors):
            ax2.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.004,
                f"{val:.3f}", ha="center", va="bottom",
                fontsize=10, fontweight="bold",
            )

        plt.tight_layout()
        return self._savefig("class_priors.png")

    # ── 7. Comparison with baseline methods ─────────────────────────────────

    @staticmethod
    def _rule_based_predict(text: str) -> str:
        """Simple keyword-based classifier used as a baseline."""
        lower = text.lower()
        words = set(lower.split())

        select_kw = {
            "покажи", "показать", "выведи", "вывести", "найди", "найти",
            "получи", "получить", "отобрази", "show", "find", "get",
            "list", "select", "retrieve", "display", "search",
        }
        insert_kw = {
            "добавь", "добавить", "создай", "создать", "вставь", "вставить",
            "зарегистрируй", "insert", "add", "create", "register",
        }
        update_kw = {
            "обнови", "обновить", "измени", "изменить", "поменяй", "поменять",
            "установи", "update", "change", "modify", "set",
        }
        delete_kw = {
            "удали", "удалить", "убери", "убрать", "стереть", "исключить",
            "delete", "remove", "drop", "erase",
        }

        # Priority order: DELETE > UPDATE > INSERT > SELECT
        if words & delete_kw: return "DELETE"
        if words & update_kw: return "UPDATE"
        if words & insert_kw: return "INSERT"
        if words & select_kw: return "SELECT"
        return "SELECT"   # default

    def plot_baseline_comparison(self, classifier, test_data: list) -> str:
        texts      = [t for t, _ in test_data]
        true_lbl   = [l for _, l in test_data]
        n          = len(true_lbl)
        n_classes  = len(set(true_lbl))

        # Baselines
        random_acc       = 1.0 / n_classes
        always_sel_acc   = sum(1 for l in true_lbl if l == "SELECT") / n
        rule_preds       = [self._rule_based_predict(t) for t in texts]
        rule_acc         = sum(1 for p, t in zip(rule_preds, true_lbl) if p == t) / n
        nb_preds         = [classifier.predict(t) for t in texts]
        nb_acc           = sum(1 for p, t in zip(nb_preds, true_lbl) if p == t) / n

        methods = ["Случайный\nвыбор", "Всегда\nSELECT", "Правила\n(keywords)", "Наивный\nБайес ★"]
        values  = [random_acc * 100, always_sel_acc * 100, rule_acc * 100, nb_acc * 100]
        colors  = ["#90A4AE", "#90A4AE", "#FFB74D", "#4CAF50"]

        fig, ax = plt.subplots(figsize=(10, 6))
        bars = ax.bar(methods, values, color=colors, alpha=0.87,
                      edgecolor="white", width=0.5)
        ax.axhline(
            nb_acc * 100, color="#2E7D32", linestyle="--", linewidth=2,
            label=f"Наш результат: {nb_acc * 100:.1f}%",
        )
        ax.set_ylabel("Точность (%)", fontsize=12)
        ax.set_title(
            "График 7: Сравнение классификатора с базовыми методами",
            fontsize=13, fontweight="bold",
        )
        ax.set_ylim(0, 115)
        ax.legend(fontsize=11)
        ax.grid(axis="y", alpha=0.4)

        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1.5,
                f"{val:.0f}%", ha="center", va="bottom",
                fontsize=11, fontweight="bold",
            )

        plt.tight_layout()
        return self._savefig("baseline_comparison.png")

    # ── 8. Log-probability scores for one example query ─────────────────────

    def plot_query_log_scores(
        self, classifier, query: str, title: str = None
    ) -> str:
        """
        Shows the raw log P(class | query) scores from MultinomialNB.
        The winning class bar is coloured; the rest are greyed out.
        """
        log_probs = classifier.pipeline.predict_log_proba([query])[0]
        classes   = list(classifier.classes_)
        best_idx  = int(np.argmax(log_probs))
        best_cls  = classes[best_idx]

        bar_colors = [
            _CLASS_COLORS.get(cls, "#90A4AE") if cls == best_cls else "#CFD8DC"
            for cls in classes
        ]

        fig, ax = plt.subplots(figsize=(9, 5))
        bars = ax.bar(classes, log_probs, color=bar_colors, alpha=0.87, edgecolor="white")

        ax.set_xlabel("Класс (интент)", fontsize=12)
        ax.set_ylabel("log score", fontsize=12)
        display = f'«{query}»' if len(query) <= 48 else f'«{query[:45]}...»'
        heading = title or "График 8: Оценки классификатора"
        ax.set_title(f"{heading}\n{display}", fontsize=13, fontweight="bold")
        ax.grid(axis="y", alpha=0.4)

        # Add value labels slightly below bar top
        span = max(log_probs) - min(log_probs)
        for bar, val in zip(bars, log_probs):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                val - span * 0.04,
                f"{val:.2f}", ha="center", va="top",
                fontsize=10, fontweight="bold",
            )

        plt.tight_layout()
        return self._savefig("query_log_scores.png")

    # ── Full report (8 plots) ────────────────────────────────────────────────

    def generate_full_report(
        self,
        classifier,
        test_data: list,
        audit_results: list,
        example_query: str = "Покажи всех сотрудников из Москвы",
    ) -> list[str]:
        """Generate all 8 metric plots; return list of saved file paths."""
        texts  = [t for t, _ in test_data]
        y_true = [l for _, l in test_data]
        y_pred = [classifier.predict(t) for t in texts]
        labels = sorted(set(y_true))

        cv        = classifier.cross_validate()
        cv_scores = cv["cv_scores"]

        paths = [
            self.plot_classification_metrics(y_true, y_pred, labels),  # 1
            self.plot_confusion_matrix(y_true, y_pred, labels),        # 2
            self.plot_security_distribution(audit_results),            # 3
            self.plot_cv_scores(cv_scores),                            # 4
            self.plot_top_features(classifier),                        # 5
            self.plot_class_priors(classifier),                        # 6
            self.plot_baseline_comparison(classifier, test_data),      # 7
            self.plot_query_log_scores(classifier, example_query),     # 8
        ]
        return paths