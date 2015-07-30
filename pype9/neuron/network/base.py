"""

  This package mirrors the one in pyNN

  Author: Thomas G. Close (tclose@oist.jp)
  Copyright: 2012-2014 Thomas G. Close.
  License: This file is part of the "NineLine" package, which is released under
           the MIT Licence, see LICENSE for details.
"""
# This is required to ensure that the right MPI variables are set before
# NEURON is initiated
from __future__ import absolute_import
from pyNN.neuron import setup
try:
    from mpi4py import MPI  # @UnresolvedImport @UnusedImport
except:
    pass
from pyNN.common.control import build_state_queries
import pyNN.neuron.simulator as simulator
import neuron
import logging
from .population import Population
from .projection import Projection
from pype9.base.network import Network as BaseNetwork

logger = logging.getLogger("PyPe9")

get_current_time, get_time_step, get_min_delay, \
    get_max_delay, num_processes, rank = build_state_queries(simulator)


class Network(BaseNetwork):

    _PopulationClass = Population
    _ProjectionClass = Projection

    def __init__(self, filename, build_mode='lazy', timestep=None,
                 min_delay=None, max_delay=None, temperature=None,
                 silent_build=False, flags=[], solver_name=None, rng=None):
        # Sets the 'get_min_delay' function for use in the network init
        self.get_min_delay = get_min_delay
        # Call the base function initialisation function.
        BaseNetwork.__init__(
            self, filename, build_mode=build_mode, timestep=timestep,
            min_delay=min_delay, max_delay=max_delay, temperature=temperature,
            silent_build=silent_build, flags=flags, solver_name=solver_name,
            rng=rng)

    def _set_simulation_params(self, **params):
        """
        Sets the simulation parameters either from the passed parameters or
        from the nineml description

        @param params[**kwargs]: Parameters that are either passed to the pyNN
                                 setup method or set explicitly
        """
        p = self._get_simulation_params(**params)
        setup(p['timestep'], p['min_delay'], p['max_delay'])
        neuron.h.celsius = p['temperature']
