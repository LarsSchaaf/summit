from .base import Strategy, Transform
from .random import LHS
from summit.domain import *
from summit.utils.dataset import DataSet
from summit.utils.thompson_sampling import ThompsonSampledModel
from scipy import optimize
import numpy as np
from typing import Callable, Tuple, Union, Optional


class CBBO(Strategy):
    """Bayesian Optimisation

    This strategy enables pre-training a model with past reaction data
    in order to enable faster optimisation.

    Parameters
    ----------

    domain : :class:`~summit.domain.Domain`
        The domain of the optimization
    transform : :class:`~summit.strategies.base.Transform`, optional
        A transform object. By default no transformation will be done
        on the input variables or objectives.
    pretraining_data : :class:`~summit.utils.data.DataSet`
        A DataSet with pretraining data. Must contain a metadata column named "task"
        that specfies the task for all data.
    task : int, optional
        The index of the task being optimized. Defaults to 1.
    categorical_method : str, optional
        The method for transforming categorical variables. Either
        "one-hot" or "descriptors". Descriptors must be included in the
        categorical variables for the later.

    Notes
    -----


    References
    ----------

    Examples
    --------

    >>> from summit.domain import Domain, ContinuousVariable
    >>> from summit.strategies import NelderMead
    >>> domain = Domain()
    >>> domain += ContinuousVariable(name='temperature', description='reaction temperature in celsius', bounds=[0, 1])
    >>> domain += ContinuousVariable(name='flowrate_a', description='flow of reactant a in mL/min', bounds=[0, 1])
    >>> domain += ContinuousVariable(name="yld", description='relative conversion to xyz', bounds=[0,100], is_objective=True, maximize=True)
    >>> strategy = NelderMead(domain)
    >>> next_experiments  = strategy.suggest_experiments()
    >>> print(next_experiments)
    NAME temperature flowrate_a             strategy
    TYPE        DATA       DATA             METADATA
    0          0.500      0.500  Nelder-Mead Simplex
    1          0.625      0.500  Nelder-Mead Simplex
    2          0.500      0.625  Nelder-Mead Simplex

    """

    def __init__(
        self,
        domain: Domain,
        transform: Transform = None,
        categorical_method: str = "one-hot",
        **kwargs,
    ):
        Strategy.__init__(self, domain, transform, **kwargs)
        self.categorical_method = categorical_method
        if self.categorical_method not in ["one-hot", "descriptors"]:
            raise ValueError(
                "categorical_method must be one of 'one-hot' or 'descriptors'."
            )
        self.reset()

    def suggest_experiments(self, num_experiments, prev_res: DataSet = None, **kwargs):
        q = num_experiments
        if q < 2:
            raise ValueError("CBBO requires at least 2 experiments")

        # Suggest lhs initial design or append new experiments to previous experiments
        if prev_res is None:
            lhs = LHS(self.domain)
            self.iterations += 1
            k = num_experiments if num_experiments > 1 else 2
            conditions = lhs.suggest_experiments(k)
            return conditions
        elif prev_res is not None and self.all_experiments is None:
            self.all_experiments = prev_res
        elif prev_res is not None and self.all_experiments is not None:
            self.all_experiments = self.all_experiments.append(prev_res)
        self.iterations += 1
        data = self.all_experiments

        # Get inputs (decision variables) and outputs (objectives)
        inputs, output = self.transform.transform_inputs_outputs(
            data,
            categorical_method=self.categorical_method,
            standardize_inputs=True,
            standardize_outputs=True,
        )

        # Train and sample model
        samples = []
        models = []
        for j in range(q):
            model = ThompsonSampledModel("test_model_{j}")
            model.fit(
                inputs,
                output,
                n_retries=10,
                # CHANGE BACK TO 1500
                n_spectral_points=1500,
            )
            models.append(model)

        # Optimize Thompson sampled function
        # q is batch size
        # m is the input space dimension
        objective = self.domain.output_variables[0]
        if objective.maximize:
            maximize = True
        else:
            maximize = False

        def f_opt(X, models, m, q):
            X = np.reshape(X, (q, m))
            f = np.sum([model.rff(xs) for xs, model in zip(X, models)])
            if maximize:
                f *= -1.0
            return f

        bounds = self._get_bounds() * q
        restarts = 50
        x0s = [
            [b[0] + np.random.rand() * (b[1] - b[0]) for b in bounds]
            for _ in range(restarts)
        ]
        m = len(self.domain.input_variables)
        res_x, res_y = multi_start_optimize(
            f_opt, x0s, func_args=(models, m, q), bounds=bounds
        )
        results = res_x.reshape((q, m))

        # Convert result to datset
        result = DataSet(
            results,
            columns=inputs.data_columns,
        )

        # Untransform
        result = self.transform.un_transform(
            result, categorical_method=self.categorical_method, standardize_inputs=True
        )

        # Add metadata
        result[("strategy", "METADATA")] = "STBO"
        return result

    def _get_bounds(self):
        bounds = []
        for v in self.domain.input_variables:
            if isinstance(v, ContinuousVariable):
                mean = self.transform.input_means[v.name]
                std = self.transform.input_stds[v.name]
                v_bounds = np.array(v.bounds)
                v_bounds = (v_bounds - mean) / std
                bounds.append(v_bounds)
            elif (
                isinstance(v, CategoricalVariable)
                and self.categorical_method == "one-hot"
            ):
                bounds += [[0, 1] for _ in v.levels]
        return bounds

    def reset(self):
        """Reset MTBO state"""
        self.all_experiments = None
        self.iterations = 0

    @staticmethod
    def standardize(X):
        mean, std = X.mean(), X.std()
        std[std < 1e-5] = 1e-5
        scaled = (X - mean.to_numpy()) / std.to_numpy()
        return scaled.to_numpy(), mean, std


def multi_start_optimize(
    fun: Callable[[np.ndarray], float], x0s: np.ndarray, func_args, **kwargs
) -> Tuple[np.ndarray, float]:
    """
    Helper function to run fmin-optimization from many start points.
    Parameters
    ----------
    fun : callable
        the function to minimize
    x0s : numpy.ndarray
        (N_starts, D) array of initial guesses
    Returns
    -------
    x_best : numpy.ndarray
        (D,) coordinate of the found minimum
    y_best : float
        function value at the minimum

    Notes
    ------
    Copied from pyrff

    """
    x_peaks = [optimize.minimize(fun, x0=x0, args=func_args, **kwargs).x for x0 in x0s]
    y_peaks = [fun(x, *func_args) for x in x_peaks]
    ibest = np.argmin(y_peaks)
    return x_peaks[ibest], y_peaks[ibest]