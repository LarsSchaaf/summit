from summit.utils.dataframe import zero_one_scale_df
import numpy as np
import pandas as pd
from typing import List, Optional, Type
from abc import ABC, abstractmethod

class Variable(ABC):
    """A base class for variables
    
    Parameters
    ----------
    name: str
        The name of the variable
    description: str
        A short description of the variable

    Attributes
    ---------
    name
    description
    """
    def __init__(self, name: str, description: str, variable_type: str):
        Variable._check_name(name)
        self._name = name
        self._description = description
        self._variable_type = variable_type

    @property
    def name(self)-> str:
        """str: name of the variable"""
        return self._name

    @name.setter
    def name(self, value: str):
        Variable._check_name(value)
        self._name = value

    @property
    def description(self) -> str:
        """str: description of the variable"""
        return self._description

    @description.setter
    def description(self, value: str):
        self._description = value

    @property
    def variable_type(self) -> str:
        return self._variable_type
    
    @staticmethod
    def _check_name(name: str):
        if type(name) != str:
            raise ValueError(f"""{name} is not a string. Variable names must be strings.""")

        test_name = name
        if name != test_name.replace(" ", ""):
            raise ValueError(f"""Error with variable name "{name}". Variable names cannot have spaces. Try replacing spaces with _ or -""")

    def __repr__(self):
        return f"Variable(name={self.name}, description={self.description})"

    @abstractmethod
    def _html_table_rows(self):
        pass

    def _make_html_table_rows(self, value):
        name_column = f"<td>{self.name}</td>"
        type_column = f"<td>{self.variable_type}</td>"
        description_column = f"<td>{self.description}</td>"
        values_column = f"<td>{value}</td>"
        return f"<tr>{name_column}{type_column}{description_column}{values_column}</tr>"



class ContinuousVariable(Variable):
    """Representation of a continuous variable
    
    Parameters
    ----------
    name: str
        The name of the variable
    description: str
        A short description of the variable 
    bounds: list of float or int
        The lower and upper bounds (respectively) of the variable

    Attributes
    ---------
    name
    description
    bounds
    lower_bound
    upper_bound

    Examples
    --------
    >>> var = ContinuousVariable('temperature', 'reaction temperature', [1, 100])

    """

    def __init__(self, name: str, description: str, bounds: list):
        Variable.__init__(self, name, description, 'continuous')
        self._lower_bound = bounds[0]
        self._upper_bound = bounds[1]

    @property
    def bounds(self):
        """`numpy.ndarray`: Lower and upper bound of the variable"""
        return np.array([self.lower_bound, self.upper_bound])

    @property
    def lower_bound(self):
        """float or int: lower bound of the variable"""
        return self._lower_bound

    @property
    def upper_bound(self):
        """float or int: upper bound of the variable"""
        return self._upper_bound

    def _html_table_rows(self):
        return self._make_html_table_rows(f"[{self.lower_bound},{self.upper_bound}]")

    
class DiscreteVariable(Variable):
    """Representation of a discrete variable
    
    Parameters
    ----------
    name: str
        The name of the variable
    description: str
        A short description of the variable 
    levels: list of any serializable object
        The potential values of the discrete variable

    Attributes
    ---------
    name
    description
    levels

    Examples
    --------
    >>> reactant = DiscreteVariable('reactant', 'aromatic reactant', ['benzene', 'toluene'])

    """
    def __init__(self, name, description, levels):
        Variable.__init__(self, name, description, 'discrete')
        
        #check that levels are unique
        if len(list({v for v in levels})) != len(levels):
            raise ValueError("Levels must have unique values.")
        self._levels = levels

    @property
    def levels(self) -> np.ndarray:
        """`numpy.ndarray`: Potential values of the discrete variable"""
        levels = np.array(self._levels)
        return np.atleast_2d(levels).T

    @property
    def num_levels(self) -> int:
        return len(self._levels)

    def add_level(self, level):
        """ Add a level to the discrete variable

        Parameters
        ---------
        level
            Value to add to the levels of the discrete variable

        Raises
        ------
        ValueError
            If the level is already in the list of levels
        """
        if level in self._levels:
            raise ValueError("Levels must have unique values.")
        self._levels.append(level)

    def remove_level(self, level):
        """ Add a level to the discrete variable

        Parameters
        ---------
        level
            Level to remove from the discrete variable

        Raises
        ------
        ValueError
            If the level does not exist for the discrete variable
        """
        try:
            remove_index = self._levels.index(level)
        except ValueError:
            raise ValueError(f"Level {level} is not in the list of levels.")

    def _html_table_rows(self):
        return self._make_html_table_rows(f"{self.num_levels} levels")

class DescriptorsVariable(Variable):
    """Representation of a set of descriptors
    
    Parameters
    ----------
    name: str
        The name of the variable
    description: str
        A short description of the variable 
    df: pandas.DataFrame
        A pandas dataframe with the values of descriptors
    select_subset: numpy.ndarray, optional
        A subset of index values in the df that should be selected from in all designs and optimizations

    Attributes
    ---------
    name
    description
    df
    select_subset
    num_descriptors
    num_examples

    Notes
    -----
    In other places, this type of variable is called a bandit variable. 

    Examples
    --------
    >>> solvent_df = pd.DataFrame([[5, 81],[-93, 111]], 
                                  index=['benzene', 'toluene'],
                                  columns=['melting_point', 'boiling_point'])
    >>> solvent = DescriptorsVariable('solvent', 'solvent descriptors', solvent_df)
    """    
    def __init__(self, name: str, description: str, 
                 df: pd.DataFrame, 
                 select_subset: np.ndarray= None):
        Variable.__init__(self, name, description, 'descriptors')
        self.df = df
        self._normalized = zero_one_scale_df(self.df)
        self.select_subset = select_subset

    @property
    def num_descriptors(self) -> int:
        return self.df.shape[1]

    @property
    def num_examples(self):
        return self.df.shape[0]
    
    @property
    def normalized(self):
        return self._normalized 

    def _html_table_rows(self):
        return self._make_html_table_rows(f"{self.num_examples} examples of {self.num_descriptors} descriptors")

class Domain:
    """Representation of the optimization domain

    Parameters
    ---------
    variables: list of `Variable` like objects, optional
        list of variable objects (i.e., `ContinuousVariable`, `DiscreteVariable`, `DescriptorsVariable`)

    Attributes
    ----------
    variables

    Examples
    --------
    >>> domain = Domain()
    >>> domain += ContinuousVariable('temperature', 'reaction temperature', [1, 100])

    """
    def __init__(self, variables:Optional[List[Type[Variable]]]=[]):
        self._variables = variables

    @property
    def variables(self):
        """[List[Type[Variable]]]: List of variables in the domain"""
        return self._variables

    @property
    def num_variables(self) -> int:
        """int: Number of variables in the domain"""
        return len(self.variables)

    @property
    def num_discrete_variables(self) -> int:
        """int: Number of discrete variables in the domain"""
        discrete_bool = [variable.variable_type == 'discrete'
                         for variable in self._variables]
        return discrete_bool.count(True)

    @property
    def num_continuous_dimensions(self) -> int:
        """int: The number of continuous dimensions, including dimensions of descriptors variables"""
        k = 0
        for v in self._variables:
            if v.variable_type == 'continuous':
                k+=1
            if v.variable_type == 'descriptors':
                k+= v.num_descriptors
        return k
    
    def __add__(self, var):
        # assert type(var) == Variable
        self._variables.append(var)
        return self
    
    def _repr_html_(self):
        """Build html string for table display in jupyter notebooks.
        
        Notes
        -----
        Adapted from https://github.com/GPflow/GPflowOpt/blob/master/gpflowopt/domain.py
        """
        html = ["<table id='domain' width=100%>"]

        # Table header
        columns = ['Name', 'Type', 'Description', 'Values']
        header = "<tr>"
        header += ''.join(map(lambda l: "<td><b>{0}</b></td>".format(l), columns))
        header += "</tr>"
        html.append(header)

        # Add parameters
        html.append(self._html_table_rows())
        html.append("</table>")

        return ''.join(html)

    def _html_table_rows(self):
        return ''.join(map(lambda l: l._html_table_rows(), self._variables))

        

class DomainError(Exception):
    pass