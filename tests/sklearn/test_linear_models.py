"""Tests for the sklearn linear models."""
import numpy
import pytest
from sklearn.datasets import make_classification, make_regression
from sklearn.decomposition import PCA
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from concrete.ml.sklearn import LinearRegression, LogisticRegression

datasets = [
    pytest.param(
        LinearRegression,
        lambda: make_regression(n_samples=200, n_features=10, random_state=42),
        id="make_regression_10_features",
    ),
    pytest.param(
        LinearRegression,
        lambda: make_regression(n_samples=200, n_features=10, noise=2, random_state=42),
        id="make_regression_features_10_noise_2",
    ),
    pytest.param(
        LinearRegression,
        lambda: make_regression(n_samples=200, n_features=14, n_informative=14, random_state=42),
        id="make_regression_features_14_informative_14",
    ),
    pytest.param(
        LinearRegression,
        lambda: make_regression(
            n_samples=200, n_features=14, n_targets=2, n_informative=14, random_state=42
        ),
        id="make_regression_features_14_informative_14_targets_2",
    ),
    pytest.param(
        LogisticRegression,
        lambda: make_classification(n_samples=200, class_sep=2, n_features=10, random_state=42),
        id="make_classification_10_features",
    ),
    pytest.param(
        LogisticRegression,
        lambda: make_classification(n_samples=200, class_sep=2, n_features=14, random_state=42),
        id="make_classification_features_14_informative_14",
    ),
    pytest.param(
        LogisticRegression,
        lambda: make_classification(
            n_samples=200,
            n_features=14,
            n_clusters_per_class=1,
            class_sep=2,
            n_classes=4,
            random_state=42,
        ),
        id="make_classification_features_14_informative_14_classes_4",
    ),
]


@pytest.mark.parametrize(
    "alg, load_data",
    datasets,
)
def test_linear_model_compile_run_fhe(load_data, alg, default_compilation_configuration):
    """Tests the sklearn LinearRegression."""

    # Get the dataset
    x, y = load_data()

    # Here we fix n_bits = 2 to make sure the quantized model does not overflow
    # during the compilation.
    model = alg(n_bits=2)
    model, _ = model.fit_benchmark(x, y)

    y_pred = model.predict(x[:1])

    # Test compilation
    model.compile(x, default_compilation_configuration)

    # Make sure we can predict over a single example in FHE.
    y_pred_fhe = model.predict(x[:1], execute_in_fhe=True)

    # Check that the ouput shape is correct
    assert y_pred_fhe.shape == y_pred.shape


@pytest.mark.parametrize(
    "alg, load_data",
    datasets,
)
@pytest.mark.parametrize(
    "n_bits",
    [
        pytest.param(20, id="20_bits"),
        pytest.param(16, id="16_bits"),
    ],
)
def test_linear_model_quantization(
    alg,
    load_data,
    n_bits,
    check_r2_score,
):
    """Tests the sklearn LinearModel quantization."""

    # Get the dataset
    x, y = load_data()

    model = alg(n_bits=n_bits)
    model, sklearn_model = model.fit_benchmark(x, y)

    # Check that class prediction are similar
    y_pred_quantized = model.predict(x)
    y_pred_sklearn = sklearn_model.predict(x)
    check_r2_score(y_pred_sklearn, y_pred_quantized)

    if isinstance(model, LogisticRegression):
        # Check that probabilties are similar
        y_pred_quantized = model.predict_proba(x)
        y_pred_sklearn = sklearn_model.predict_proba(x)
        check_r2_score(y_pred_sklearn, y_pred_quantized)


def test_double_fit():
    """Tests that calling fit multiple times gives the same results"""
    x, y = make_classification()
    model = DecisionTreeClassifier()

    # First fit
    model.fit(x, y)
    y_pred_one = model.predict(x)

    # Second fit
    model.fit(x, y)
    y_pred_two = model.predict(x)

    assert numpy.array_equal(y_pred_one, y_pred_two)


@pytest.mark.parametrize(
    "alg",
    [
        pytest.param(LinearRegression),
        pytest.param(LogisticRegression),
    ],
)
def test_pipeline_sklearn(alg):
    """Tests that the linear models work well within sklearn pipelines."""
    x, y = make_classification(n_features=10, n_informative=2, n_redundant=0, n_classes=2)
    pipe_cv = Pipeline(
        [
            ("pca", PCA(n_components=2)),
            ("scaler", StandardScaler()),
            ("alg", alg()),
        ]
    )
    # Do a grid search to find the best hyperparameters
    param_grid = {
        "alg__n_bits": [2, 3],
    }
    grid_search = GridSearchCV(pipe_cv, param_grid, cv=3)
    grid_search.fit(x, y)
