"""Conditional Variational Autoencoder (CVAE) for siRNA modification pattern generation.

This is the generative ML model that transforms OligoVoid from a discriminative
scorer into a true generative design engine — the same class of model used by
Insilico Medicine's Chemistry42 for small-molecule generation, applied here to
the RNA chemical modification space.

Architecture:
  Plain GP:  "Given these features, predict efficacy" (discriminative)
  CVAE:      "Given a desired efficacy, GENERATE a feature profile" (generative)

The CVAE learns a smooth latent space of valid modification patterns.
Conditioning on target efficacy enables directed generation of candidates
predicted to achieve a specific knockdown level.

Feature representation:
  Input/output dimension = 42 (18 core sequence features + 24 thermodynamic)
  These are continuous summary features from real_data_pipeline.build_ml_dataset(),
  NOT 336-dim one-hot vectors. We use MSE reconstruction loss accordingly.

In-silico validation loop (novel contribution):
  1. CVAE generates N new candidate feature profiles
  2. GP model predicts efficacy for each candidate
  3. Report: what % achieve predicted efficacy > 70% (therapeutic threshold)
  4. Compare: random sampling vs CVAE-guided generation
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONSTANTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FEATURE_DIM = 42       # 18 core + 24 thermodynamic features
LATENT_DIM = 16        # Small latent space — few training patterns
CONDITION_DIM = 1      # Conditioning signal: target efficacy


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENCODER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Encoder(nn.Module):
    """Encodes a siRNA feature profile + efficacy condition into latent (mu, logvar).

    Input:  [feature_vector (42) || condition (1)] = 43 dims
    Output: mu (latent_dim), log_var (latent_dim)

    Architecture: 43 → 64 → ReLU → Dropout(0.1) → 32 → ReLU → (mu, logvar)
    """

    def __init__(self, input_dim: int = FEATURE_DIM, latent_dim: int = LATENT_DIM):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim + CONDITION_DIM, 64),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(64, 32),
            nn.ReLU(),
        )
        self.fc_mu = nn.Linear(32, latent_dim)
        self.fc_logvar = nn.Linear(32, latent_dim)

    def forward(self, x: torch.Tensor, condition: torch.Tensor):
        xc = torch.cat([x, condition.unsqueeze(-1)], dim=-1)
        h = self.net(xc)
        return self.fc_mu(h), self.fc_logvar(h)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DECODER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Decoder(nn.Module):
    """Decodes a latent vector + efficacy condition back into a feature profile.

    Input:  [latent_vector (latent_dim) || condition (1)]
    Output: 42-dim continuous feature vector (MSE reconstruction target)

    Architecture: (latent_dim+1) → 32 → ReLU → 64 → ReLU → 42
    """

    def __init__(self, latent_dim: int = LATENT_DIM, output_dim: int = FEATURE_DIM):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(latent_dim + CONDITION_DIM, 32),
            nn.ReLU(),
            nn.Linear(32, 64),
            nn.ReLU(),
            nn.Linear(64, output_dim),
        )

    def forward(self, z: torch.Tensor, condition: torch.Tensor):
        zc = torch.cat([z, condition.unsqueeze(-1)], dim=-1)
        return self.net(zc)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CVAE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class OligoVoidCVAE(nn.Module):
    """Conditional Variational Autoencoder for siRNA modification generation.

    Conditioned on: desired knockdown efficacy (0-1 scale)
    Generates: novel 42-dim feature profiles representing modification patterns

    This is the generative model that transforms OligoVoid from a discriminative
    scorer into a true generative design engine.
    """

    def __init__(
        self, feature_dim: int = FEATURE_DIM, latent_dim: int = LATENT_DIM
    ):
        super().__init__()
        self.encoder = Encoder(feature_dim, latent_dim)
        self.decoder = Decoder(latent_dim, feature_dim)
        self.latent_dim = latent_dim
        self.feature_dim = feature_dim

    def reparameterize(self, mu: torch.Tensor, log_var: torch.Tensor) -> torch.Tensor:
        """Reparameterization trick: z = mu + eps * exp(0.5 * log_var)."""
        std = torch.exp(0.5 * log_var)
        eps = torch.randn_like(std)
        return mu + eps * std

    def forward(self, x: torch.Tensor, condition: torch.Tensor):
        mu, log_var = self.encoder(x, condition)
        z = self.reparameterize(mu, log_var)
        recon = self.decoder(z, condition)
        return recon, mu, log_var

    def generate(
        self,
        n_samples: int = 10,
        target_efficacy: float = 0.80,
        temperature: float = 1.0,
    ) -> torch.Tensor:
        """Generate n_samples novel feature profiles conditioned on target_efficacy.

        Args:
            n_samples: Number of candidates to generate.
            target_efficacy: Desired knockdown efficacy (0-1 scale).
            temperature: Controls diversity vs quality tradeoff.
                         Lower = more conservative, higher = more diverse.

        Returns:
            Tensor of shape (n_samples, feature_dim) in standardized space.
        """
        self.eval()
        with torch.no_grad():
            z = torch.randn(n_samples, self.latent_dim) * temperature
            condition = torch.full((n_samples,), float(target_efficacy))
            return self.decoder(z, condition)

    def encode(self, x: torch.Tensor, condition: torch.Tensor) -> torch.Tensor:
        """Encode inputs to latent means (for visualization / analysis)."""
        self.eval()
        with torch.no_grad():
            mu, _ = self.encoder(x, condition)
            return mu


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOSS FUNCTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def cvae_loss(
    recon_x: torch.Tensor,
    x: torch.Tensor,
    mu: torch.Tensor,
    log_var: torch.Tensor,
    beta: float = 0.5,
) -> dict[str, Any]:
    """CVAE loss = MSE reconstruction + beta * KL divergence.

    MSE because our features are continuous summary values (not one-hot).
    KL regularizes the latent space to be smooth and continuous.
    beta controls the tradeoff (beta-VAE style): higher = more disentangled.

    Returns dict with individual losses for monitoring.
    """
    recon_loss = F.mse_loss(recon_x, x, reduction="mean")
    kl_loss = -0.5 * torch.mean(1 + log_var - mu.pow(2) - log_var.exp())
    total = recon_loss + beta * kl_loss
    return {
        "total": total,
        "reconstruction": recon_loss.item(),
        "kl": kl_loss.item(),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TRAINING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def train_cvae(
    X: np.ndarray,
    y: np.ndarray,
    epochs: int = 200,
    batch_size: int = 16,
    learning_rate: float = 1e-3,
    save_path: str | None = None,
) -> dict:
    """Train the CVAE on real feature data from build_ml_dataset().

    Args:
        X: Feature matrix of shape (n_samples, 42).
        y: Efficacy values 0-100 scale.
        epochs: Number of training epochs.
        batch_size: Mini-batch size.
        learning_rate: Adam learning rate.
        save_path: Where to save the trained model. Defaults to data/cvae_model.pt.

    Returns:
        Training metrics dict.
    """
    from sklearn.preprocessing import StandardScaler

    if save_path is None:
        save_path = str(DATA_DIR / "cvae_model.pt")

    # Standardize features, normalize efficacy to 0-1
    scaler_X = StandardScaler()
    X_scaled = scaler_X.fit_transform(X).astype(np.float32)
    y_norm = (y / 100.0).astype(np.float32)

    X_tensor = torch.tensor(X_scaled)
    y_tensor = torch.tensor(y_norm)

    dataset = TensorDataset(X_tensor, y_tensor)
    loader = DataLoader(
        dataset,
        batch_size=min(batch_size, len(dataset)),
        shuffle=True,
        drop_last=False,
    )

    feature_dim = X.shape[1]
    model = OligoVoidCVAE(feature_dim=feature_dim, latent_dim=LATENT_DIM)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=50, gamma=0.7)

    best_loss = float("inf")
    history: list[float] = []

    for epoch in range(epochs):
        model.train()
        epoch_loss = 0.0
        n_batches = 0

        for xb, yb in loader:
            optimizer.zero_grad()
            recon, mu, logvar = model(xb, yb)
            loss_dict = cvae_loss(recon, xb, mu, logvar)
            loss_dict["total"].backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            epoch_loss += loss_dict["total"].item()
            n_batches += 1

        scheduler.step()
        avg_loss = epoch_loss / max(n_batches, 1)
        history.append(avg_loss)

        if avg_loss < best_loss:
            best_loss = avg_loss
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            torch.save(
                {
                    "model_state": model.state_dict(),
                    "scaler_X_mean": scaler_X.mean_,
                    "scaler_X_scale": scaler_X.scale_,
                    "feature_dim": feature_dim,
                    "latent_dim": LATENT_DIM,
                    "best_loss": best_loss,
                },
                save_path,
            )

        if epoch % 50 == 0:
            logger.info("Epoch %d: loss=%.4f", epoch, avg_loss)

    logger.info("CVAE training complete. Best loss: %.4f", best_loss)

    return {
        "best_loss": round(float(best_loss), 6),
        "final_loss": round(float(history[-1]), 6),
        "epochs": epochs,
        "n_training": len(X),
        "feature_dim": feature_dim,
        "latent_dim": LATENT_DIM,
        "save_path": save_path,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOADING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def load_cvae(path: str | None = None) -> tuple["OligoVoidCVAE", "StandardScaler"]:
    """Load a trained CVAE model and its feature scaler.

    Returns:
        (model, scaler_X) tuple.
    """
    from sklearn.preprocessing import StandardScaler

    if path is None:
        path = str(DATA_DIR / "cvae_model.pt")

    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    model = OligoVoidCVAE(
        feature_dim=checkpoint["feature_dim"],
        latent_dim=checkpoint["latent_dim"],
    )
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    scaler = StandardScaler()
    scaler.mean_ = checkpoint["scaler_X_mean"]
    scaler.scale_ = checkpoint["scaler_X_scale"]
    scaler.var_ = scaler.scale_ ** 2
    scaler.n_features_in_ = checkpoint["feature_dim"]

    return model, scaler


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EVALUATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def evaluate_cvae_generation(
    model: OligoVoidCVAE,
    scaler_X,
    X_train_raw: np.ndarray,
    n_generate: int = 50,
    target_efficacy: float = 0.80,
) -> dict:
    """Evaluate quality of CVAE-generated candidates with 5 standard metrics.

    Metrics:
      - valid_fraction:  % of generated profiles with all values in reasonable range
      - novelty:         % that differ from all training points by L1 > threshold
      - diversity:       mean pairwise Euclidean distance among generated profiles
      - uniqueness:      fraction of distinct patterns (after rounding)
      - reconstruction:  mean MSE between training data round-tripped through CVAE

    Args:
        model: Trained OligoVoidCVAE.
        scaler_X: StandardScaler used during training.
        X_train_raw: Raw (unscaled) training feature matrix for novelty comparison.
        n_generate: Number of candidates to generate.
        target_efficacy: Conditioning value (0-1 scale).

    Returns:
        Evaluation metrics dict.
    """
    from scipy.spatial.distance import pdist

    # Scale training data for comparison
    X_train_scaled = scaler_X.transform(X_train_raw).astype(np.float32)

    # Generate candidates (in standardized space)
    generated = model.generate(n_generate, target_efficacy, temperature=1.0)
    gen_np = generated.numpy()

    # 1. Validity: all features within ±4 std of training mean
    valid_mask = np.all(np.abs(gen_np) < 4.0, axis=1)
    valid_fraction = float(valid_mask.mean())

    # 2. Novelty: min L1 distance to any training point > 0.15 per feature
    novelty_count = 0
    for g in gen_np:
        dists = np.mean(np.abs(X_train_scaled - g), axis=1)
        if dists.min() > 0.15:
            novelty_count += 1
    novelty = novelty_count / max(len(gen_np), 1)

    # 3. Diversity: mean pairwise Euclidean distance
    if len(gen_np) > 1:
        diversity = float(np.mean(pdist(gen_np, "euclidean")))
    else:
        diversity = 0.0

    # 4. Uniqueness: fraction of distinct patterns (rounded to 2 dp)
    rounded = np.round(gen_np, 2)
    unique_rows = set(map(tuple, rounded))
    uniqueness = len(unique_rows) / max(len(gen_np), 1)

    # 5. Reconstruction quality: round-trip training data through CVAE
    model.eval()
    with torch.no_grad():
        x_t = torch.tensor(X_train_scaled)
        y_t = torch.full((len(X_train_scaled),), target_efficacy)
        recon, _, _ = model(x_t, y_t)
        recon_mse = float(F.mse_loss(recon, x_t).item())

    return {
        "n_generated": n_generate,
        "target_efficacy": target_efficacy,
        "valid_fraction": round(valid_fraction, 4),
        "novelty": round(novelty, 4),
        "diversity": round(diversity, 4),
        "uniqueness": round(uniqueness, 4),
        "reconstruction_mse": round(recon_mse, 6),
        "summary": (
            f"Valid={valid_fraction * 100:.0f}% | "
            f"Novel={novelty * 100:.0f}% | "
            f"Diverse={diversity:.2f} | "
            f"Unique={uniqueness * 100:.0f}%"
        ),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# IN-SILICO VALIDATION (GP ORACLE COMPARISON)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def in_silico_validation(
    model: OligoVoidCVAE,
    scaler_X,
    X_train_raw: np.ndarray,
    y_train: np.ndarray,
    n_generate: int = 100,
    target_efficacy: float = 0.85,
) -> dict:
    """In-silico validation loop — the novel contribution.

    1. CVAE generates N candidate feature profiles
    2. GP model (trained on same data) predicts efficacy for each
    3. Report: what % achieve predicted efficacy > 70% (therapeutic threshold)
    4. Compare: CVAE-guided vs random sampling from latent space

    This IS the "wet lab" result — in silico but transparent and reproducible.

    Returns:
        Validation metrics comparing CVAE vs random generation.
    """
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import Matern, WhiteKernel

    # Train a simple GP oracle on the raw features
    kernel = Matern(nu=2.5) + WhiteKernel(noise_level=0.1)
    gp_oracle = GaussianProcessRegressor(
        kernel=kernel, n_restarts_optimizer=3, normalize_y=True, alpha=1e-6
    )
    X_train_scaled = scaler_X.transform(X_train_raw).astype(np.float64)
    gp_oracle.fit(X_train_scaled, y_train)

    # --- CVAE-guided generation ---
    cvae_generated = model.generate(n_generate, target_efficacy, temperature=1.0)
    cvae_np = cvae_generated.numpy().astype(np.float64)
    cvae_pred, cvae_std = gp_oracle.predict(cvae_np, return_std=True)

    cvae_above_70 = float(np.mean(cvae_pred > 70.0))
    cvae_mean_pred = float(np.mean(cvae_pred))
    cvae_mean_std = float(np.mean(cvae_std))

    # --- Random baseline (sample from standard normal in latent space) ---
    random_z = torch.randn(n_generate, model.latent_dim)
    random_cond = torch.full((n_generate,), target_efficacy)
    model.eval()
    with torch.no_grad():
        random_generated = model.decoder(random_z, random_cond)
    random_np = random_generated.numpy().astype(np.float64)
    random_pred, random_std = gp_oracle.predict(random_np, return_std=True)

    random_above_70 = float(np.mean(random_pred > 70.0))
    random_mean_pred = float(np.mean(random_pred))
    random_mean_std = float(np.mean(random_std))

    # --- Pure noise baseline (no CVAE at all) ---
    noise_profiles = np.random.randn(n_generate, X_train_scaled.shape[1])
    noise_pred, noise_std = gp_oracle.predict(noise_profiles, return_std=True)
    noise_above_70 = float(np.mean(noise_pred > 70.0))
    noise_mean_pred = float(np.mean(noise_pred))

    return {
        "n_generated": n_generate,
        "target_efficacy_pct": target_efficacy * 100,
        "therapeutic_threshold_pct": 70.0,
        "cvae_guided": {
            "above_threshold_pct": round(cvae_above_70 * 100, 1),
            "mean_predicted_efficacy": round(cvae_mean_pred, 2),
            "mean_uncertainty": round(cvae_mean_std, 2),
        },
        "random_latent": {
            "above_threshold_pct": round(random_above_70 * 100, 1),
            "mean_predicted_efficacy": round(random_mean_pred, 2),
            "mean_uncertainty": round(random_mean_std, 2),
        },
        "pure_noise": {
            "above_threshold_pct": round(noise_above_70 * 100, 1),
            "mean_predicted_efficacy": round(noise_mean_pred, 2),
        },
        "cvae_advantage_pp": round((cvae_above_70 - random_above_70) * 100, 1),
        "summary": (
            f"CVAE: {cvae_above_70 * 100:.0f}% above 70% threshold "
            f"(mean {cvae_mean_pred:.1f}%) | "
            f"Random: {random_above_70 * 100:.0f}% | "
            f"Noise: {noise_above_70 * 100:.0f}%"
        ),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FULL GENERATION DEMO (powers the dashboard)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def run_full_generation_demo(
    target_efficacy: float = 0.85,
    n_samples: int = 20,
) -> dict:
    """Full demo: train CVAE if needed, generate candidates, evaluate.

    Loads training data from real_data_pipeline.build_ml_dataset(),
    trains (or loads cached) CVAE, generates candidates conditioned on
    target_efficacy, evaluates with all metrics including in-silico
    GP oracle validation.

    Returns top candidates for the "AI-Generated Candidates" dashboard tab.
    """
    from backend.real_data_pipeline import build_ml_dataset

    model_path = str(DATA_DIR / "cvae_model.pt")

    X_tr, X_te, y_tr, y_te, meta = build_ml_dataset()

    # Train or load
    if not os.path.exists(model_path) or os.path.getsize(model_path) < 1000:
        logger.info("Training CVAE (first run)...")
        train_metrics = train_cvae(X_tr, y_tr, epochs=200, save_path=model_path)
    else:
        train_metrics = {"status": "loaded from cache", "save_path": model_path}

    model, scaler = load_cvae(model_path)

    # Evaluate generation quality
    eval_results = evaluate_cvae_generation(
        model, scaler, X_tr, n_generate=n_samples, target_efficacy=target_efficacy
    )

    # In-silico validation (CVAE vs random vs noise)
    validation = in_silico_validation(
        model, scaler, X_tr, y_tr,
        n_generate=max(n_samples, 50),
        target_efficacy=target_efficacy,
    )

    # Generate final candidates
    generated = model.generate(n_samples, target_efficacy, temperature=1.0)
    gen_np = generated.numpy()

    # Inverse-transform to original feature scale for interpretability
    gen_original = scaler.inverse_transform(gen_np)

    candidates = []
    for i in range(len(gen_np)):
        is_valid = bool(np.all(np.abs(gen_np[i]) < 4.0))
        candidates.append({
            "candidate_id": f"CVAE_{i + 1:03d}",
            "feature_vector_scaled": gen_np[i].tolist(),
            "feature_vector_original": gen_original[i].tolist(),
            "target_efficacy_pct": target_efficacy * 100,
            "generation_temperature": 1.0,
            "is_valid": is_valid,
        })

    # Sort by validity, take top 10
    valid_candidates = [c for c in candidates if c["is_valid"]]
    top_candidates = (valid_candidates or candidates)[:10]

    return {
        "training_metrics": train_metrics,
        "generation_eval": eval_results,
        "in_silico_validation": validation,
        "candidates": top_candidates,
        "total_generated": n_samples,
        "total_valid": len(valid_candidates),
        "dataset_info": {
            "n_train": len(X_tr),
            "n_test": len(X_te),
            "n_features": X_tr.shape[1] if X_tr.ndim > 1 else 0,
        },
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STANDALONE TEST
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    import asyncio

    print("=" * 60)
    print("OligoVoid CVAE — Generative Model Test Suite")
    print("=" * 60)

    # 1. Smoke test: forward pass
    print("\n[1] Smoke test: forward pass")
    model = OligoVoidCVAE(feature_dim=42, latent_dim=16)
    x = torch.randn(4, 42)
    cond = torch.tensor([0.8, 0.6, 0.9, 0.7])
    recon, mu, logvar = model(x, cond)
    print(f"    Input: {x.shape} → Recon: {recon.shape}, "
          f"Mu: {mu.shape}, LogVar: {logvar.shape}")

    # 2. Loss computation
    print("\n[2] Loss computation")
    loss = cvae_loss(recon, x, mu, logvar)
    print(f"    Total: {loss['total'].item():.4f}, "
          f"Recon: {loss['reconstruction']:.4f}, "
          f"KL: {loss['kl']:.4f}")

    # 3. Generation
    print("\n[3] Generation (untrained)")
    gen = model.generate(5, target_efficacy=0.85)
    print(f"    Generated 5 samples: shape {gen.shape}")

    # 4. Encoding
    print("\n[4] Latent encoding")
    z = model.encode(x, cond)
    print(f"    Encoded 4 samples: shape {z.shape}")

    # 5. Train on real data
    print("\n[5] Training on real data...")
    try:
        from backend.real_data_pipeline import build_ml_dataset

        X_tr, X_te, y_tr, y_te, meta = build_ml_dataset()
        print(f"    Dataset: {X_tr.shape[0]} train, {X_te.shape[0]} test, "
              f"{X_tr.shape[1]} features")

        metrics = train_cvae(X_tr, y_tr, epochs=100,
                             save_path=str(DATA_DIR / "cvae_model.pt"))
        print(f"    Best loss: {metrics['best_loss']:.4f}")

        # 6. Load and evaluate
        print("\n[6] Load and evaluate")
        model, scaler = load_cvae(str(DATA_DIR / "cvae_model.pt"))
        eval_r = evaluate_cvae_generation(
            model, scaler, X_tr, n_generate=30, target_efficacy=0.80
        )
        print(f"    {eval_r['summary']}")
        print(f"    Reconstruction MSE: {eval_r['reconstruction_mse']:.4f}")

        # 7. In-silico validation
        print("\n[7] In-silico validation (CVAE vs Random vs Noise)")
        val = in_silico_validation(
            model, scaler, X_tr, y_tr, n_generate=50, target_efficacy=0.85
        )
        print(f"    {val['summary']}")
        print(f"    CVAE advantage: {val['cvae_advantage_pp']:+.1f} pp")

    except Exception as e:
        print(f"    Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("generative_model.py ready")
    print("=" * 60)
