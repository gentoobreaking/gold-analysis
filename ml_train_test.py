#!/usr/bin/env python3
# NOTE: this script intentionally uses the canonical backend.app.ml modules.
# It is a training/validation utility, not a legacy duplicate — keep it.
"""
ml_train_test.py - 測試 gold-analysis ML 模組
串接 FeatureEngineer → ModelTrainer → ModelEvaluator
看 309 筆台灣銀行金價資料能訓練出什麼效果

輸入：gold_monitor_pro.db（local_sell 當收盤價）
輸出：訓練結果 + 評估報告
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

# 載入 ML 模組
sys.path.insert(0, str(Path(__file__).parent))
from backend.app.ml.feature_engineering import FeatureEngineer
from backend.app.ml.model_evaluator import ModelEvaluator
from backend.app.ml.model_trainer import ModelTrainer, TrainingConfig


def main():
    print("=" * 60)
    print("🌟 Gold Analysis ML 訓練測試")
    print("=" * 60)

    # ── 1. 讀取資料 ──────────────────────────────────────────────
    db_path = Path.home() / ".qclaw" / "gold_monitor_pro.db"
    print(f"\n📂 讀取: {db_path}")
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT timestamp, local_sell, local_buy, international_spot, exchange_rate "
        "FROM price_history WHERE metal='gold' ORDER BY timestamp ASC"
    ).fetchall()
    conn.close()
    print(f"   共 {len(rows)} 筆資料")

    if len(rows) < 60:
        print("⚠️ 資料太少，無法訓練（至少需要 60 筆）")
        return

    # ── 2. 轉換格式 ──────────────────────────────────────────────
    # 台灣銀行 local_sell 當收盤價
    df = pd.DataFrame(
        rows, columns=["date", "close", "local_buy", "international_spot", "exchange_rate"]
    )
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["close"])

    print(f"   日期範圍: {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}")
    print(f"   有效資料: {len(df)} 筆")

    # ── 3. 特徵工程 ──────────────────────────────────────────────
    print("\n📐 執行特徵工程...")
    engineer = FeatureEngineer()
    df_features = engineer.fit_transform(df)

    feature_names = engineer.get_feature_names()
    print(f"   生成 {len(feature_names)} 個特徵")
    print(f"   有效樣本: {len(df_features)} 筆")

    # 標籤分佈
    label_map = {-1: "SELL", 0: "HOLD", 1: "BUY"}
    for label_val, label_name in label_map.items():
        count = (df_features["label"] == label_val).sum()
        pct = count / len(df_features) * 100
        print(f"   {label_name}: {count} ({pct:.1f}%)")

    if len(df_features) < 50:
        print("⚠️ 有效樣本太少，訓練終止")
        return

    # ── 4. 訓練模型 ──────────────────────────────────────────────
    print("\n🧠 訓練 Random Forest 模型...")
    X = df_features[feature_names]
    y = df_features["label"]

    trainer = ModelTrainer()
    config = TrainingConfig(
        model_type="random_forest",
        test_size=0.2,
        random_state=42,
        cv_folds=5,
    )
    result = trainer.train(X, y, config=config, feature_names=feature_names)

    print("\n📊 訓練結果:")
    print(f"   模型: {result.model_name} {result.version}")
    print(f"   訓練準確率: {result.train_accuracy:.4f}")
    print(f"   驗證準確率: {result.val_accuracy:.4f}")
    print(f"   交叉驗證: {result.cv_mean:.4f} ± {result.cv_std:.4f}")
    print(f"   訓練時間: {result.trained_at}")

    # 精選指標
    metrics = result.metrics
    print(f"   Precision: {metrics.get('precision', 0):.4f}")
    print(f"   Recall: {metrics.get('recall', 0):.4f}")
    print(f"   F1: {metrics.get('f1', 0):.4f}")

    # Top 5 特徵重要性
    print("\n🔑 Top 5 重要特徵:")
    importance = result.feature_importance
    if importance:
        sorted_imp = sorted(importance.items(), key=lambda x: x[1], reverse=True)
        for i, (name, score) in enumerate(sorted_imp[:5], 1):
            print(f"   {i}. {name}: {score:.4f}")

    # ── 5. 評估 ──────────────────────────────────────────────────
    print("\n📊 模型評估...")
    split_idx = int(len(X) * 0.8)
    X_val = X.iloc[split_idx:]
    y_val = y.iloc[split_idx:]

    y_pred = trainer.predict(X_val)
    y_proba = None
    try:
        y_proba = trainer.predict_proba(X_val)
    except Exception:
        pass

    evaluator = ModelEvaluator()
    report = evaluator.evaluate_classification(
        y_true=y_val.values,
        y_pred=y_pred,
        y_proba=y_proba,
        model_name=result.model_name,
        version=result.version,
    )

    print(evaluator.print_report(report))

    # ── 6. 即時預測（最新一天） ──────────────────────────────────
    print("\n🔮 即時預測（最新一天）:")
    latest = df_features.iloc[-1:]
    latest_features = latest[feature_names]
    pred = trainer.predict(latest_features)
    label_name = label_map.get(int(pred[0]), "?")
    print(f"   預測: {label_name}")
    print(f"   日期: {df_features.iloc[-1]['date']}")

    try:
        proba = trainer.predict_proba(latest_features)
        classes = trainer.current_model.classes_
        print("   機率: ", end="")
        for cls, p in zip(classes, proba[0]):
            print(f"{label_map.get(cls, cls)}={p:.2%} ", end="")
        print()
    except Exception:
        pass

    print("\n✅ 完成")


if __name__ == "__main__":
    main()
