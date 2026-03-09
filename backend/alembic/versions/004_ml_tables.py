"""Add ML model registry, training runs, and predictions tables.

Revision ID: 004
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ml_models",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("model_type", sa.String(50), nullable=False, index=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("name", sa.String(200)),
        sa.Column("status", sa.String(20), server_default="trained"),
        sa.Column("is_active", sa.Boolean, server_default="false"),
        sa.Column("architecture", JSONB),
        sa.Column("hyperparameters", JSONB),
        sa.Column("feature_config", JSONB),
        sa.Column("train_date_from", sa.String(10)),
        sa.Column("train_date_to", sa.String(10)),
        sa.Column("val_date_from", sa.String(10)),
        sa.Column("val_date_to", sa.String(10)),
        sa.Column("test_date_from", sa.String(10)),
        sa.Column("test_date_to", sa.String(10)),
        sa.Column("train_samples", sa.Integer),
        sa.Column("val_samples", sa.Integer),
        sa.Column("test_samples", sa.Integer),
        sa.Column("train_metrics", JSONB),
        sa.Column("val_metrics", JSONB),
        sa.Column("test_metrics", JSONB),
        sa.Column("model_path", sa.String(500)),
        sa.Column("scaler_path", sa.String(500)),
        sa.Column("training_time_seconds", sa.Numeric(10, 2)),
        sa.Column("inference_time_ms", sa.Numeric(8, 2)),
        sa.Column("file_size_mb", sa.Numeric(8, 2)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "ml_training_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ml_model_id", sa.Integer, sa.ForeignKey("ml_models.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("status", sa.String(20), server_default="running"),
        sa.Column("progress", sa.String(300)),
        sa.Column("current_epoch", sa.Integer),
        sa.Column("total_epochs", sa.Integer),
        sa.Column("epoch_history", JSONB),
        sa.Column("best_epoch", sa.Integer),
        sa.Column("best_val_loss", sa.Numeric(10, 6)),
        sa.Column("best_val_metric", sa.Numeric(10, 6)),
        sa.Column("config_snapshot", JSONB),
        sa.Column("error_message", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "ml_predictions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ml_model_id", sa.Integer, sa.ForeignKey("ml_models.id", ondelete="SET NULL"), index=True),
        sa.Column("model_type", sa.String(50), nullable=False, index=True),
        sa.Column("ticker_id", sa.Integer, sa.ForeignKey("tickers.id"), nullable=False, index=True),
        sa.Column("prediction_date", sa.Date, nullable=False, index=True),
        sa.Column("prediction", JSONB, nullable=False),
        sa.Column("ensemble_score", sa.Numeric(5, 2)),
        sa.Column("rule_based_score", sa.Numeric(5, 2)),
        sa.Column("nn_score", sa.Numeric(5, 2)),
        sa.Column("actual_outcome", sa.String(20)),
        sa.Column("actual_return", sa.Numeric(8, 4)),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Add nn_score columns to signals table
    op.add_column("signals", sa.Column("nn_score", sa.Numeric(5, 2)))
    op.add_column("signals", sa.Column("nn_confidence", sa.Numeric(5, 4)))
    op.add_column("signals", sa.Column("scoring_mode", sa.String(20)))


def downgrade() -> None:
    op.drop_column("signals", "scoring_mode")
    op.drop_column("signals", "nn_confidence")
    op.drop_column("signals", "nn_score")
    op.drop_table("ml_predictions")
    op.drop_table("ml_training_runs")
    op.drop_table("ml_models")
