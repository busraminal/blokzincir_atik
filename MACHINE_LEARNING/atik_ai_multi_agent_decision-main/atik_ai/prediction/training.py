"""
ATIK AI - Model Training
Bi-Encoder eğitim pipeline

PR Model: Produce tahminlemesi
NR Model: Need tahminlemesi
"""
import logging
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass
import numpy as np

import torch
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW
from torch.nn import BCELoss

from tqdm import tqdm

from .encoders import BiEncoder, EncoderConfig
from ..core.exceptions import PredictionError

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Eğitim konfigürasyonu"""
    batch_size: int = 32
    learning_rate: float = 2e-5
    epochs: int = 10
    warmup_steps: int = 100
    weight_decay: float = 0.01
    max_grad_norm: float = 1.0
    eval_steps: int = 100
    save_steps: int = 500
    output_dir: str = "./models"
    early_stopping_patience: int = 3


class WasteDataset(Dataset):
    """
    Waste prediction dataset
    
    Her örnek: (activity_desc, waste_name, label)
    """
    
    def __init__(
        self,
        activity_descriptions: List[str],
        waste_names: List[str],
        labels: List[int],
        cpc_descriptions: List[str] = None
    ):
        assert len(activity_descriptions) == len(waste_names) == len(labels)
        
        self.activities = activity_descriptions
        self.wastes = waste_names
        self.labels = labels
        self.cpc = cpc_descriptions or [None] * len(labels)
    
    def __len__(self):
        return len(self.labels)
    
    def __getitem__(self, idx):
        return {
            "activity": self.activities[idx],
            "waste": self.wastes[idx],
            "cpc": self.cpc[idx],
            "label": float(self.labels[idx])
        }


def collate_fn(batch):
    """DataLoader collate function"""
    return {
        "activities": [item["activity"] for item in batch],
        "wastes": [item["waste"] for item in batch],
        "cpc": [item["cpc"] for item in batch],
        "labels": torch.tensor([item["label"] for item in batch])
    }


class Trainer:
    """
    Bi-Encoder Eğitici
    """
    
    def __init__(
        self,
        model: BiEncoder,
        config: TrainingConfig = None,
        device: str = None
    ):
        self.model = model
        self.config = config or TrainingConfig()
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        
        self.model.to(self.device)
        
        # Optimizer
        self.optimizer = AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay
        )
        
        # Loss
        self.criterion = BCELoss()
        
        # Tracking
        self.train_losses = []
        self.eval_losses = []
        self.best_eval_loss = float('inf')
        self.patience_counter = 0
    
    def train(
        self,
        train_dataset: WasteDataset,
        eval_dataset: WasteDataset = None
    ) -> Dict:
        """
        Model eğitimi
        
        Returns:
            Training metrics
        """
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.batch_size,
            shuffle=True,
            collate_fn=collate_fn
        )
        
        eval_loader = None
        if eval_dataset:
            eval_loader = DataLoader(
                eval_dataset,
                batch_size=self.config.batch_size,
                shuffle=False,
                collate_fn=collate_fn
            )
        
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        global_step = 0
        
        for epoch in range(self.config.epochs):
            self.model.train()
            epoch_loss = 0.0
            
            progress = tqdm(train_loader, desc=f"Epoch {epoch + 1}/{self.config.epochs}")
            
            for batch in progress:
                # Forward
                predictions = self.model(
                    batch["activities"],
                    batch["wastes"],
                    batch["cpc"]
                ).squeeze()
                
                labels = batch["labels"].to(self.device)
                
                # Loss
                loss = self.criterion(predictions, labels)
                
                # Backward
                self.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config.max_grad_norm)
                self.optimizer.step()
                
                epoch_loss += loss.item()
                global_step += 1
                
                progress.set_postfix({"loss": loss.item()})
                
                # Evaluation
                if eval_loader and global_step % self.config.eval_steps == 0:
                    eval_loss = self.evaluate(eval_loader)
                    self.eval_losses.append(eval_loss)
                    
                    # Early stopping check
                    if eval_loss < self.best_eval_loss:
                        self.best_eval_loss = eval_loss
                        self.patience_counter = 0
                        # Save best model
                        self.save(output_dir / "best_model.pt")
                    else:
                        self.patience_counter += 1
                    
                    if self.patience_counter >= self.config.early_stopping_patience:
                        logger.info(f"Early stopping at step {global_step}")
                        break
                
                # Save checkpoint
                if global_step % self.config.save_steps == 0:
                    self.save(output_dir / f"checkpoint_{global_step}.pt")
            
            avg_loss = epoch_loss / len(train_loader)
            self.train_losses.append(avg_loss)
            logger.info(f"Epoch {epoch + 1} - Average Loss: {avg_loss:.4f}")
            
            # Early stopping
            if self.patience_counter >= self.config.early_stopping_patience:
                break
        
        # Final save
        self.save(output_dir / "final_model.pt")
        
        return {
            "train_losses": self.train_losses,
            "eval_losses": self.eval_losses,
            "best_eval_loss": self.best_eval_loss,
            "total_steps": global_step
        }
    
    def evaluate(self, eval_loader: DataLoader) -> float:
        """Değerlendirme"""
        self.model.eval()
        total_loss = 0.0
        
        with torch.no_grad():
            for batch in eval_loader:
                predictions = self.model(
                    batch["activities"],
                    batch["wastes"],
                    batch["cpc"]
                ).squeeze()
                
                labels = batch["labels"].to(self.device)
                loss = self.criterion(predictions, labels)
                total_loss += loss.item()
        
        avg_loss = total_loss / len(eval_loader)
        self.model.train()
        
        return avg_loss
    
    def compute_metrics(self, eval_dataset: WasteDataset) -> Dict:
        """Metrikler hesapla"""
        self.model.eval()
        
        all_preds = []
        all_labels = []
        
        eval_loader = DataLoader(
            eval_dataset,
            batch_size=self.config.batch_size,
            shuffle=False,
            collate_fn=collate_fn
        )
        
        with torch.no_grad():
            for batch in eval_loader:
                predictions = self.model(
                    batch["activities"],
                    batch["wastes"],
                    batch["cpc"]
                ).squeeze()
                
                all_preds.extend(predictions.cpu().numpy())
                all_labels.extend(batch["labels"].numpy())
        
        all_preds = np.array(all_preds)
        all_labels = np.array(all_labels)
        
        # Binary predictions
        binary_preds = (all_preds > 0.5).astype(int)
        
        # Metrics
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
        
        metrics = {
            "accuracy": accuracy_score(all_labels, binary_preds),
            "precision": precision_score(all_labels, binary_preds, zero_division=0),
            "recall": recall_score(all_labels, binary_preds, zero_division=0),
            "f1": f1_score(all_labels, binary_preds, zero_division=0),
            "auc_roc": roc_auc_score(all_labels, all_preds) if len(np.unique(all_labels)) > 1 else 0
        }
        
        return metrics
    
    def save(self, path: str):
        """Model kaydet"""
        torch.save(self.model.state_dict(), path)
        logger.debug(f"Model kaydedildi: {path}")
    
    def load(self, path: str):
        """Model yükle"""
        self.model.load_state_dict(torch.load(path, map_location=self.device))
        logger.info(f"Model yüklendi: {path}")


def create_synthetic_dataset(
    n_samples: int = 1000,
    positive_ratio: float = 0.5
) -> WasteDataset:
    """
    Test için sentetik dataset oluştur
    """
    activities = [
        "Manufacture of textiles",
        "Processing of agricultural products",
        "Metal casting and forming",
        "Chemical production",
        "Food and beverage processing"
    ]
    
    wastes = [
        "textile waste",
        "organic residue",
        "metal scrap",
        "chemical sludge",
        "food waste"
    ]
    
    n_positive = int(n_samples * positive_ratio)
    n_negative = n_samples - n_positive
    
    data_activities = []
    data_wastes = []
    labels = []
    
    # Positive samples (eşleşen çiftler)
    for _ in range(n_positive):
        idx = np.random.randint(len(activities))
        data_activities.append(activities[idx])
        data_wastes.append(wastes[idx])
        labels.append(1)
    
    # Negative samples (eşleşmeyen çiftler)
    for _ in range(n_negative):
        idx1 = np.random.randint(len(activities))
        idx2 = np.random.randint(len(wastes))
        while idx2 == idx1:
            idx2 = np.random.randint(len(wastes))
        data_activities.append(activities[idx1])
        data_wastes.append(wastes[idx2])
        labels.append(0)
    
    # Shuffle
    indices = np.random.permutation(n_samples)
    
    return WasteDataset(
        [data_activities[i] for i in indices],
        [data_wastes[i] for i in indices],
        [labels[i] for i in indices]
    )
