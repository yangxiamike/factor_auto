from factor_autoresearch.data_loader import DataLoader


def test_data_loader_loads_fixture(sample_dataset_dir, test_config) -> None:
    dataset = DataLoader().load(sample_dataset_dir, test_config)
    assert list(dataset.panel.index.names) == ["trade_date", "ts_code"]
    assert {"fwd_ret_1d", "fwd_ret_5d", "fwd_ret_20d"} <= set(dataset.forward_returns.columns)
