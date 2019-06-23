"""
A large portion of this code is inspired by or copied from GPFlowOpt, which 
is Apache Licensed (open-soruce)
https://github.com/GPflow/GPflowOpt/blob/master/gpflowopt/optim.py

"""
from typing import List
from summit.domain import Domain
from summit.initial_design import RandomDesigner
from .objective import ObjectiveWrapper

import numpy as np
from scipy.optimize import OptimizeResult


class Optimizer(ABC):
    def __init__(self, domain: Domain):
        self._domain = domain
        self._multiobjective = False

    def optimize(self, objectivefx, **kwargs):
        '''  Optimize the objective
        
        Parameters
        ---------- 
        models: List
            Should be a model or a list of models to optimize.
        
        Returns
        -------
        result: DataSet
            The result of the optimization as a DataSet
        
        Raises
        ------
        ValueError
            If multiple models are passed but the optimization method 
            is not multiobjective
               
        ''' 
        objective = ObjectiveWrapper(objectivefx, **self._wrapper_args)
        try:
            result = self._optimize(objective, **kwargs)
        except KeyboardInterrupt:
            result = OptimizeResult(x=objective._previous_x,
                                    success=False,
                                    message="Caught KeyboardInterrupt, returning last good value.")
        result.nfev = objective.counter
        return result

    @abstractmethod
    def _optimize(self, models):
        raise NotImplementedError('The Optimize class is not meant to be used directly. Instead use one of the specific optimizers such as NSGAII.')

    @property
    def is_multiobjective(self):
        '''Return true if the algorithm does multiobjective optimization'''
        return self._multiobjective

class NSGAII(Optimizer): 
    # TODO: Liwei Cao will implement this 
    def _optimize(self):
        raise NotImplementedError("NSGAII optimizer not yet implemented")

class MCOptimizer(Optimizer):
    """
    Optimization of an objective function by evaluating a set of random points.
    Note: each call to optimize, a different set of random points is evaluated.
    """

    def __init__(self, domain, nsamples):
        """
        :param domain: Optimization :class:`~.domain.Domain`.
        :param nsamples: number of random points to use
        """
        Optimizer.__init__(domain)
        self._nsamples = nsamples
        # Clear the initial data points
        self.set_initial(np.empty((0, self.domain.size)))

    @Optimizer.domain.setter
    def domain(self, dom):
        self._domain = dom

    def _get_eval_points(self):
        r =  RandomDesigner(self.domain)
        return r.generate_experiments(self._nsamples)

    def _optimize(self, objective):
        points = self._get_eval_points()
        evaluations = objective(points)
        idx_best = np.argmin(evaluations, axis=0)

        return OptimizeResult(x=points[idx_best, :],
                              success=True,
                              fun=evaluations[idx_best, :],
                              nfev=points.shape[0],
                              message="OK")

    def set_initial(self, initial):
        initial = np.atleast_2d(initial)
        if initial.size > 0:
            warnings.warn("Initial points set in {0} are ignored.".format(self.__class__.__name__), UserWarning)
            return

        super(MCOptimizer, self).set_initial(initial)

class CandidateOptimizer(MCOptimizer):
    """
    Optimization of an objective function by evaluating a set of pre-defined candidate points.
    Returns the point with minimal objective value.
    """

    def __init__(self, domain, candidates):
        """
        :param domain: Optimization :class:`~.domain.Domain`.
        :param candidates: candidate points, should be within the optimization domain.
        """
        MCOptimizer.__init__(self, domain, candidates.shape[0])
        assert (candidates in domain)
        self.candidates = candidates

    def _get_eval_points(self):
        return self.candidates

    @MCOptimizer.domain.setter
    def domain(self, dom):
        t = self.domain >> dom
        super(CandidateOptimizer, self.__class__).domain.fset(self, dom)
        self.candidates = t.forward(self.candidates)