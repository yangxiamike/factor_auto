import pandas as pd

from factor_autoresearch.compute_v1.panel import PanelStore
from factor_autoresearch.data_loader import DataLoader


def test_panel_store_round_trips_field_to_legacy_series(sample_dataset_dir, test_config) -> None:
    dataset = DataLoader(config=test_config, dataset_path=sample_dataset_dir).load()
    store = PanelStore.from_dataset(dataset)

    result = store.to_series("close_hfq", store.field("close_hfq")).reindex(dataset.panel.index)

    pd.testing.assert_series_equal(result, dataset.panel["close_hfq"].rename("close_hfq"))
    assert store.universe_mask.shape == store.field("close_hfq").shape
