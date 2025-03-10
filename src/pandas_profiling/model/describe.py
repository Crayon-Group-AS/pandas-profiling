"""Organize the calculation of statistics for each series in this DataFrame."""
import warnings
from datetime import datetime
from typing import Optional

import pandas as pd
from tqdm.auto import tqdm

from pandas_profiling.config import config as config
from pandas_profiling.model.correlations import calculate_correlation
from pandas_profiling.model.duplicates import get_duplicates
from pandas_profiling.model.sample import Sample, get_sample
from pandas_profiling.model.summary import (
    get_messages,
    get_missing_diagrams,
    get_scatter_matrix,
    get_series_descriptions,
    get_table_stats,
)
from pandas_profiling.model.typeset import Numeric, Unsupported
from pandas_profiling.version import __version__


def describe(
    title: str, df: pd.DataFrame, summarizer, typeset, sample: Optional[dict] = None
) -> dict:
    """Calculate the statistics for each series in this DataFrame.

    Args:
        title: report title
        df: DataFrame.
        sample: optional, dict with custom sample

    Returns:
        This function returns a dictionary containing:
            - table: overall statistics.
            - variables: descriptions per series.
            - correlations: correlation matrices.
            - missing: missing value diagrams.
            - messages: direct special attention to these patterns in your data.
            - package: package details.
    """

    if df is None:
        raise ValueError("Can not describe a `lazy` ProfileReport without a DataFrame.")

    if not isinstance(df, pd.DataFrame):
        warnings.warn("df is not of type pandas.DataFrame")

    disable_progress_bar = not config["progress_bar"].get(bool)

    date_start = datetime.utcnow()

    correlation_names = [
        correlation_name
        for correlation_name in [
            "pearson",
            "spearman",
            "kendall",
            "phi_k",
            "cramers",
        ]
        if config["correlations"][correlation_name]["calculate"].get(bool)
    ]

    number_of_tasks = 8 + len(df.columns) + len(correlation_names)

    with tqdm(
        total=number_of_tasks, desc="Summarize dataset", disable=disable_progress_bar
    ) as pbar:
        series_description = get_series_descriptions(df, summarizer, typeset, pbar)

        pbar.set_postfix_str("Get variable types")
        variables = {
            column: description["type"]
            for column, description in series_description.items()
        }
        supported_columns = [
            column
            for column, type_name in variables.items()
            if type_name != Unsupported
        ]
        interval_columns = [
            column for column, type_name in variables.items() if type_name == Numeric
        ]
        pbar.update()

        # Get correlations
        correlations = {}
        for correlation_name in correlation_names:
            pbar.set_postfix_str(f"Calculate {correlation_name} correlation")
            correlations[correlation_name] = calculate_correlation(
                df, correlation_name, series_description
            )
            pbar.update()

        # make sure correlations is not None
        correlations = {
            key: value for key, value in correlations.items() if value is not None
        }

        # Scatter matrix
        pbar.set_postfix_str("Get scatter matrix")
        scatter_matrix = get_scatter_matrix(df, interval_columns)
        pbar.update()

        # Table statistics
        pbar.set_postfix_str("Get table statistics")
        table_stats = get_table_stats(df, series_description)
        pbar.update()

        # missing diagrams
        pbar.set_postfix_str("Get missing diagrams")
        missing = get_missing_diagrams(df, table_stats)
        pbar.update()

        # Sample
        pbar.set_postfix_str("Take sample")
        if sample is None:
            samples = get_sample(df)
        else:
            if "name" not in sample:
                sample["name"] = None
            if "caption" not in sample:
                sample["caption"] = None

            samples = [
                Sample("custom", sample["data"], sample["name"], sample["caption"])
            ]
        pbar.update()

        # Duplicates
        pbar.set_postfix_str("Locating duplicates")
        duplicates = get_duplicates(df, supported_columns)
        pbar.update()

        # Messages
        pbar.set_postfix_str("Get messages/warnings")
        messages = get_messages(table_stats, series_description, correlations)
        pbar.update()

        pbar.set_postfix_str("Get reproduction details")
        package = {
            "pandas_profiling_version": __version__,
            "pandas_profiling_config": config.dump(),
        }
        pbar.update()

        pbar.set_postfix_str("Completed")

    date_end = datetime.utcnow()

    analysis = {
        "title": title,
        "date_start": date_start,
        "date_end": date_end,
        "duration": date_end - date_start,
    }

    return {
        # Analysis metadata
        "analysis": analysis,
        # Overall dataset description
        "table": table_stats,
        # Per variable descriptions
        "variables": series_description,
        # Bivariate relations
        "scatter": scatter_matrix,
        # Correlation matrices
        "correlations": correlations,
        # Missing values
        "missing": missing,
        # Warnings
        "messages": messages,
        # Package
        "package": package,
        # Sample
        "sample": samples,
        # Duplicates
        "duplicates": duplicates,
    }
