"""Modelo de predicción sísmica basado en Machine Learning."""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, mean_absolute_error
import joblib
import os
from datetime import datetime, timedelta
from typing import Optional
from app.config import MODEL_PATH, PREDICTION_GRID_SIZE, PREDICTION_DAYS_AHEAD


class SeismicPredictor:
    """
    Modelo de predicción sísmica que analiza patrones históricos
    para estimar la probabilidad de actividad sísmica futura.

    Utiliza dos modelos:
    1. Clasificador: Predice SI/NO habrá un sismo significativo en una celda del grid
    2. Regresor: Estima la magnitud máxima esperada
    """

    def __init__(self):
        self.classifier = None
        self.regressor = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.training_metrics = {}
        self.feature_names = []

    def _create_spatial_grid(self, df: pd.DataFrame) -> pd.DataFrame:
        """Crea un grid espacial y calcula features por celda."""
        grid_size = PREDICTION_GRID_SIZE

        df = df.copy()
        df["lat_bin"] = (df["latitude"] / grid_size).round() * grid_size
        df["lon_bin"] = (df["longitude"] / grid_size).round() * grid_size

        return df

    def _compute_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula features sísmicas para cada celda del grid por ventana temporal.

        Features incluyen:
        - Frecuencia de sismos en la celda
        - Magnitud promedio, máxima, desviación estándar
        - Profundidad promedio
        - Tasa de cambio de actividad (aceleración sísmica)
        - Tiempo desde último evento significativo
        - b-value (parámetro de Gutenberg-Richter)
        - Energía acumulada liberada
        """
        df = self._create_spatial_grid(df)

        if df.empty:
            return pd.DataFrame()

        # Agrupar por celda y ventana temporal (30 días)
        df["time_window"] = pd.to_datetime(df["datetime"]).dt.to_period("M")

        features_list = []

        for (lat_bin, lon_bin, time_window), group in df.groupby(
            ["lat_bin", "lon_bin", "time_window"]
        ):
            # Features básicas
            event_count = len(group)
            mag_mean = group["magnitude"].mean()
            mag_max = group["magnitude"].max()
            mag_std = group["magnitude"].std() if len(group) > 1 else 0
            mag_min = group["magnitude"].min()
            depth_mean = group["depth"].mean() if "depth" in group.columns else 0
            depth_std = group["depth"].std() if len(group) > 1 else 0

            # Energía acumulada (escala logarítmica de magnitud)
            energy = np.sum(10 ** (1.5 * group["magnitude"] + 4.8))
            log_energy = np.log10(energy) if energy > 0 else 0

            # b-value (Gutenberg-Richter)
            b_value = self._compute_b_value(group["magnitude"].values)

            # Significancia promedio
            sig_mean = group["sig"].mean() if "sig" in group.columns else 0

            # Intervalo entre eventos
            if len(group) > 1:
                times_sorted = group["datetime"].sort_values()
                intervals = times_sorted.diff().dt.total_seconds().dropna()
                mean_interval = intervals.mean() / 3600  # En horas
                min_interval = intervals.min() / 3600
            else:
                mean_interval = 720  # Default 30 días en horas
                min_interval = 720

            features_list.append({
                "lat_bin": lat_bin,
                "lon_bin": lon_bin,
                "time_window": time_window,
                "event_count": event_count,
                "mag_mean": mag_mean,
                "mag_max": mag_max,
                "mag_min": mag_min,
                "mag_std": mag_std,
                "depth_mean": depth_mean,
                "depth_std": depth_std,
                "log_energy": log_energy,
                "b_value": b_value,
                "sig_mean": sig_mean,
                "mean_interval_hours": mean_interval,
                "min_interval_hours": min_interval,
            })

        return pd.DataFrame(features_list)

    def _compute_b_value(self, magnitudes: np.ndarray) -> float:
        """Calcula el b-value de la ley de Gutenberg-Richter."""
        if len(magnitudes) < 3:
            return 1.0  # Valor típico por defecto

        m_min = magnitudes.min()
        mean_mag = magnitudes.mean()

        if mean_mag - m_min == 0:
            return 1.0

        # Estimación de b-value por máxima verosimilitud
        b_value = np.log10(np.e) / (mean_mag - m_min)
        return min(max(b_value, 0.3), 3.0)  # Limitar a rango razonable

    def _create_training_targets(self, features_df: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
        """Crea targets: si hubo un sismo significativo en la siguiente ventana temporal."""
        df = self._create_spatial_grid(df)
        df["time_window"] = pd.to_datetime(df["datetime"]).dt.to_period("M")

        # Para cada celda y ventana, el target es si hay actividad en la siguiente ventana
        features_df = features_df.copy()
        features_df["next_window"] = features_df["time_window"].apply(
            lambda x: x + 1
        )

        # Verificar si hay actividad en la siguiente ventana
        next_activity = df.groupby(["lat_bin", "lon_bin", "time_window"]).agg(
            next_event_count=("magnitude", "count"),
            next_mag_max=("magnitude", "max"),
        ).reset_index()

        features_df = features_df.merge(
            next_activity,
            left_on=["lat_bin", "lon_bin", "next_window"],
            right_on=["lat_bin", "lon_bin", "time_window"],
            how="left",
            suffixes=("", "_next"),
        )

        # Target binario: ¿habrá un sismo >= 4.5 en la siguiente ventana?
        features_df["target_has_event"] = (
            features_df["next_mag_max"].fillna(0) >= 4.5
        ).astype(int)

        # Target de regresión: magnitud máxima en la siguiente ventana
        features_df["target_max_mag"] = features_df["next_mag_max"].fillna(0)

        return features_df

    def train(self, df: pd.DataFrame) -> dict:
        """Entrena los modelos de predicción."""
        print("Calculando features sísmicas...")
        features_df = self._compute_features(df)

        if features_df.empty or len(features_df) < 50:
            return {"error": "Datos insuficientes para entrenamiento"}

        print("Creando targets de entrenamiento...")
        training_df = self._create_training_targets(features_df, df)

        # Seleccionar features para el modelo
        self.feature_names = [
            "lat_bin", "lon_bin", "event_count", "mag_mean", "mag_max",
            "mag_min", "mag_std", "depth_mean", "depth_std", "log_energy",
            "b_value", "sig_mean", "mean_interval_hours", "min_interval_hours",
        ]

        X = training_df[self.feature_names].fillna(0)
        y_class = training_df["target_has_event"]
        y_reg = training_df["target_max_mag"]

        # Escalar features
        X_scaled = self.scaler.fit_transform(X)

        # Split entrenamiento/prueba
        X_train, X_test, y_train_c, y_test_c = train_test_split(
            X_scaled, y_class, test_size=0.2, random_state=42, stratify=y_class
        )
        _, _, y_train_r, y_test_r = train_test_split(
            X_scaled, y_reg, test_size=0.2, random_state=42
        )

        # Entrenar clasificador
        print("Entrenando clasificador (Random Forest)...")
        self.classifier = RandomForestClassifier(
            n_estimators=200,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
        self.classifier.fit(X_train, y_train_c)

        # Entrenar regresor
        print("Entrenando regresor (Gradient Boosting)...")
        self.regressor = GradientBoostingRegressor(
            n_estimators=200,
            max_depth=8,
            learning_rate=0.1,
            min_samples_split=5,
            random_state=42,
        )
        self.regressor.fit(X_train, y_train_r)

        # Métricas
        y_pred_c = self.classifier.predict(X_test)
        y_pred_r = self.regressor.predict(X_test)

        classifier_accuracy = self.classifier.score(X_test, y_test_c)
        regressor_mae = mean_absolute_error(y_test_r, y_pred_r)

        # Feature importance
        feature_importance = dict(zip(
            self.feature_names,
            self.classifier.feature_importances_.tolist()
        ))

        self.is_trained = True
        self.training_metrics = {
            "classifier_accuracy": round(classifier_accuracy, 4),
            "regressor_mae": round(regressor_mae, 4),
            "training_samples": len(X_train),
            "test_samples": len(X_test),
            "feature_importance": feature_importance,
            "positive_class_ratio": round(y_class.mean(), 4),
        }

        # Guardar modelo
        self.save_model()

        print(f"Entrenamiento completado. Accuracy: {classifier_accuracy:.4f}, MAE: {regressor_mae:.4f}")
        return self.training_metrics

    def predict(self, df: pd.DataFrame) -> list[dict]:
        """
        Genera predicciones de actividad sísmica futura.

        Retorna una lista de celdas con probabilidad de sismo significativo.
        """
        if not self.is_trained:
            return []

        features_df = self._compute_features(df)

        if features_df.empty:
            return []

        X = features_df[self.feature_names].fillna(0)
        X_scaled = self.scaler.transform(X)

        # Predicciones
        probabilities = self.classifier.predict_proba(X_scaled)[:, 1]
        predicted_magnitudes = self.regressor.predict(X_scaled)

        predictions = []
        for idx, row in features_df.iterrows():
            prob = probabilities[features_df.index.get_loc(idx)]
            pred_mag = predicted_magnitudes[features_df.index.get_loc(idx)]

            predictions.append({
                "latitude": row["lat_bin"],
                "longitude": row["lon_bin"],
                "probability": round(float(prob), 4),
                "predicted_max_magnitude": round(float(max(pred_mag, 0)), 2),
                "risk_level": self._get_risk_level(prob, pred_mag),
                "event_count_history": int(row["event_count"]),
                "historical_max_magnitude": round(float(row["mag_max"]), 2),
                "b_value": round(float(row["b_value"]), 3),
                "energy_released": round(float(row["log_energy"]), 2),
            })

        # Ordenar por probabilidad descendente
        predictions.sort(key=lambda x: x["probability"], reverse=True)
        return predictions

    def _get_risk_level(self, probability: float, magnitude: float) -> str:
        """Determina el nivel de riesgo basado en probabilidad y magnitud."""
        if probability >= 0.7 and magnitude >= 6.0:
            return "CRITICO"
        elif probability >= 0.5 and magnitude >= 5.0:
            return "ALTO"
        elif probability >= 0.3 and magnitude >= 4.0:
            return "MODERADO"
        elif probability >= 0.15:
            return "BAJO"
        else:
            return "MINIMO"

    def save_model(self):
        """Guarda el modelo entrenado en disco."""
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        model_data = {
            "classifier": self.classifier,
            "regressor": self.regressor,
            "scaler": self.scaler,
            "feature_names": self.feature_names,
            "training_metrics": self.training_metrics,
            "is_trained": self.is_trained,
        }
        joblib.dump(model_data, MODEL_PATH)
        print(f"Modelo guardado en {MODEL_PATH}")

    def load_model(self) -> bool:
        """Carga un modelo previamente entrenado."""
        if os.path.exists(MODEL_PATH):
            model_data = joblib.load(MODEL_PATH)
            self.classifier = model_data["classifier"]
            self.regressor = model_data["regressor"]
            self.scaler = model_data["scaler"]
            self.feature_names = model_data["feature_names"]
            self.training_metrics = model_data["training_metrics"]
            self.is_trained = model_data["is_trained"]
            print("Modelo cargado exitosamente.")
            return True
        return False


# Instancia global del predictor
predictor = SeismicPredictor()
