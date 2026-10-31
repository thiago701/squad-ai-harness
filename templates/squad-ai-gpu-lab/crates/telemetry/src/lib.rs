//! # SquadAI GPU Intelligence Lab — `telemetry`
//!
//! Métricas de qualidade preditiva (Precision, Recall, F1, AUROC, Brier Score, MAE, RMSE)
//! e contabilidade de overhead de IPC (JSON-RPC vs. Zero-Copy `.kdg`).

/// Métricas completas de avaliação de modelos preditivos (Seção 8.4 do Prompt Master).
#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct PredictiveQualityMetrics {
    pub precision: f64,
    pub recall: f64,
    pub f1_score: f64,
    pub auroc: f64,
    pub brier_score: f64,
    pub mae: f64,
    pub rmse: f64,
    pub false_positive_rate: f64,
    pub false_negative_rate: f64,
}

impl PredictiveQualityMetrics {
    /// Calcula Precision, Recall, F1, AUROC (via regra trapezoidal / Mann-Whitney U) e Brier Score
    /// a partir de probabilidades preditas `probs` (`[0,1]`) e rótulos reais `labels` (`bool`).
    pub fn evaluate_binary(probs: &[f32], labels: &[bool], threshold: f32) -> Self {
        assert_eq!(probs.len(), labels.len());
        let n = probs.len();
        if n == 0 {
            return Self::default();
        }

        let mut tp = 0usize;
        let mut fp = 0usize;
        let mut tn = 0usize;
        let mut fn_ = 0usize;
        let mut brier_sum = 0.0f64;
        let mut mae_sum = 0.0f64;

        for (&p, &y) in probs.iter().zip(labels.iter()) {
            let pred = p >= threshold;
            match (pred, y) {
                (true, true) => tp += 1,
                (true, false) => fp += 1,
                (false, false) => tn += 1,
                (false, true) => fn_ += 1,
            }
            let y_f = if y { 1.0f64 } else { 0.0f64 };
            let diff = (p as f64) - y_f;
            brier_sum += diff * diff;
            mae_sum += diff.abs();
        }

        let precision = if tp + fp > 0 {
            (tp as f64) / ((tp + fp) as f64)
        } else {
            0.0
        };
        let recall = if tp + fn_ > 0 {
            (tp as f64) / ((tp + fn_) as f64)
        } else {
            0.0
        };
        let f1_score = if precision + recall > 1e-12 {
            2.0 * precision * recall / (precision + recall)
        } else {
            0.0
        };
        let fpr = if fp + tn > 0 {
            (fp as f64) / ((fp + tn) as f64)
        } else {
            0.0
        };
        let fnr = if fn_ + tp > 0 {
            (fn_ as f64) / ((fn_ + tp) as f64)
        } else {
            0.0
        };

        // AUROC exata via estatística de Mann-Whitney U sobre pares (positivo, negativo)
        let mut pos_probs = Vec::new();
        let mut neg_probs = Vec::new();
        for (&p, &y) in probs.iter().zip(labels.iter()) {
            if y {
                pos_probs.push(p);
            } else {
                neg_probs.push(p);
            }
        }
        let auroc = if !pos_probs.is_empty() && !neg_probs.is_empty() {
            let mut concordant = 0.0f64;
            for &pp in &pos_probs {
                for &np in &neg_probs {
                    if pp > np {
                        concordant += 1.0;
                    } else if (pp - np).abs() < 1e-7 {
                        concordant += 0.5;
                    }
                }
            }
            concordant / ((pos_probs.len() * neg_probs.len()) as f64)
        } else {
            0.5
        };

        let brier = brier_sum / (n as f64);
        let mae = mae_sum / (n as f64);
        let rmse = brier.sqrt();

        Self {
            precision,
            recall,
            f1_score,
            auroc,
            brier_score: brier,
            mae,
            rmse,
            false_positive_rate: fpr,
            false_negative_rate: fnr,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_binary_evaluation_metrics() {
        let probs = vec![0.92, 0.85, 0.78, 0.15, 0.08, 0.12];
        let labels = vec![true, true, true, false, false, false];
        let m = PredictiveQualityMetrics::evaluate_binary(&probs, &labels, 0.5);
        assert!((m.precision - 1.0).abs() < 1e-6);
        assert!((m.recall - 1.0).abs() < 1e-6);
        assert!((m.f1_score - 1.0).abs() < 1e-6);
        assert!((m.auroc - 1.0).abs() < 1e-6);
        assert!(m.brier_score < 0.03);
    }
}
