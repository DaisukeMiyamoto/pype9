from __future__ import print_function
import nineml.units as un
from argparse import ArgumentParser
import ninemlcatalog
import quantities as pq
import numpy as np
import neo

min_delay = 0.1
max_delay = 10.0


def construct_reference(input_signal, dt):
    params = {
        'a': 0.2,
        'b': 0.025,
        'c': -75.0,
        'd': 0.2,
        'V_th': -50.0,
        'U_m': -14.0,
        'V_m': -70.0}
    cell = nest.Create('izhikevich', 1, params)
    generator = nest.Create(
        'step_current_generator', 1,
        {'amplitude_values': pq.Quantity(input_signal, 'pA'),
         'amplitude_times': (input_signal.times.rescale(pq.ms) -
                             min_delay * pq.ms),
         'start': float(input_signal.t_start.rescale(pq.ms)),
         'stop': float(input_signal.t_stop.rescale(pq.ms))})
    nest.Connect(generator, cell, syn_spec={'delay': min_delay})
    multimeter = nest.Create('multimeter', 1, {"interval": dt})
    nest.SetStatus(multimeter, {'record_from': ['V_m']})
    nest.Connect(multimeter, cell)
    return (cell, multimeter, generator)


parser = ArgumentParser()
parser.add_argument('--fast_spiking', action='store_true', default=False,
                    help=("Whether to use the \"fast-spiking\" version of the "
                          "Izhikevich neuron or not"))
parser.add_argument('--simtime', type=float, default=200.0,
                    help="The length of the simulation in ms")
parser.add_argument('--timestep', type=float, default=0.001,
                    help="Simulation timestep")
parser.add_argument('--simulators', type=str, nargs='+',
                    default=['neuron', 'nest'],
                    help="Which simulators to simulate the 9ML network")
parser.add_argument('--plot_start', type=float, default=0.0,
                    help=("The time to start plotting from"))
parser.add_argument('--build_mode', type=str, default='lazy',
                    help=("The build mode with which to construct the network."
                          " 'lazy' will only regenerate and compile the "
                          "source files if the network has changed, whereas "
                          "'force' will always rebuild the network"))
parser.add_argument('--seed', type=int, default=None,
                    help="Random seed passed to the simulators")
parser.add_argument('--reference', action='store_true', default=False,
                    help="Plot a reference NEST implementation alongside")
parser.add_argument('--save_fig', type=str, default=None,
                    help=("Location to save the generated figures"))
parser.add_argument('--figsize', nargs=2, type=float, default=(10, 15),
                    help="The size of the figures")
parser.add_argument('--input_start', type=float, default=50.0,
                    help="Time step input current starts")
parser.add_argument('--input_amplitude', type=float, default=None,
                    help="Amplitude of the input current step (pA)")
args = parser.parse_args()


if __name__ == "__main__":

    if args.reference and args.fast_spiking:
        raise Exception(
            "--reference and --fast_spiking options cannot be used together as"
            " there is no reference implementation for the fast-spiking model")

    # Set the random seed
    np.random.seed(args.seed)
    seeds = np.asarray(
        np.floor(np.random.random(len(args.simulators)) * 1e5), dtype=int)

    # Set of simulators to run
    simulators_to_run = set(args.simulators)
    if args.reference:
        simulators_to_run.add('nest')

    pype9_metaclass = {}
    pype9_simulation = {}
    if 'neuron' in simulators_to_run:
        from pype9.simulator.neuron import (
            CellMetaClass as CellMetaClassNEURON,
            simulation as simulationNEURON)
        pype9_simulation['neuron'] = simulationNEURON
        pype9_metaclass['neuron'] = CellMetaClassNEURON
    if 'nest' in simulators_to_run:
        import nest
        from pype9.simulator.nest import (
            CellMetaClass as CellMetaClassNEST,
            simulation as simulationNEST)
        pype9_simulation['nest'] = simulationNEST
        pype9_metaclass['nest'] = CellMetaClassNEST

    if args.fast_spiking:
        model = ninemlcatalog.load('neuron/Izhikevich',
                                   'IzhikevichFastSpiking')
        name = 'IzhikevichFastSpiking'
        properties = ninemlcatalog.load('neuron/Izhikevich',
                                        'SampleIzhikevichFastSpiking')
        initial_regime = 'subVb'
        initial_states = {'U': -1.625 * pq.pA, 'V': -70.0 * pq.mV}
        input_port_name = 'iSyn'
        if args.input_amplitude is None:
            input_amp = 100 * pq.pA
        else:
            input_amp = args.input_amplitude * pq.pA
        cell_kwargs = {'external_currents': ['iSyn']}
    else:
        name = 'IzhikevichOriginal'
        model = ninemlcatalog.load('neuron/Izhikevich', 'Izhikevich')
        properties = ninemlcatalog.load('neuron/Izhikevich',
                                        'SampleIzhikevich')
        initial_regime = 'subthreshold_regime'
        initial_states = {'U': -14.0 * pq.mV / pq.ms, 'V': -70.0 * pq.mV}
        input_port_name = 'Isyn'
        if args.input_amplitude is None:
            input_amp = 15 * pq.pA
        else:
            input_amp = args.input_amplitude * pq.pA
        cell_kwargs = {}  # Isyn should be guessed as an external current

    # Create an input step current
    num_preceding = int(np.floor(args.input_start / args.timestep))
    num_remaining = int(np.ceil((args.simtime - args.input_start) /
                                args.timestep))
    amplitude = float(pq.Quantity(input_amp, 'nA'))
    input_signal = neo.AnalogSignal(
        np.concatenate((np.zeros(num_preceding),
                        np.ones(num_remaining) * amplitude)),
        sampling_period=args.timestep * pq.ms, units='nA', time_units='ms')

    for simulator, seed in zip(simulators_to_run, seeds):
        with pype9_simulation(min_delay=min_delay, max_delay=max_delay,
                              dt=args.timestep * un.ms,
                              seed=seed) as sim:
            # Construct the cells and set up recordings and input plays
            cells = {}
            if simulator in args.simulators:
                cells[simulator] = pype9_metaclass[simulator](
                    model, name=name, default_properties=properties,
                    initial_regime=initial_regime, **cell_kwargs)()
                # Play input current into cell
                cells[simulator].play(input_port_name, input_signal)
                # Record voltage
                cells[simulator].record('V')
                # Set initial state
                cells[simulator].update_state(initial_states)
            if args.reference:
                ref_cell, ref_multi, ref_input = construct_reference(
                    input_signal, args.timestep)
            sim.run(args.simtime * un.ms)

    # Plot the results
    if args.save_fig is not None:
        import matplotlib
        matplotlib.use('pdf')
    # Needs to be imported after the args.save_fig argument is parsed to
    # allow the backend to be set
    from matplotlib import pyplot as plt  # @IgnorePep8

    print("Plotting the results")
    plt.figure(figsize=args.figsize)
    if args.fast_spiking:
        title = "Izhikevich Fast Spiking"
    else:
        title = "Izhikevich Original"
    plt.title(title)
    legend = []
    for simulator in args.simulators:
        v = cells[simulator].recording('V')
        inds = v.times > args.plot_start
        plt.plot(v.times[inds], v[inds])
        legend.append(simulator.upper())
    if args.reference:
        events, interval = nest.GetStatus(
            ref_multi, ["events", 'interval'])[0]
        t, v = np.asarray(events['times']), np.asarray(events['V_m'])
        inds = t > args.plot_start
        plt.plot(t[inds], v[inds])
        legend.append('Ref. NEST')
    plt.xlabel('Time (ms)')
    plt.ylabel('Membrane Voltage (mV)')
    plt.legend(legend)
    if args.save_fig is not None:
        plt.savefig(args.save_fig)
    else:
        plt.show()
    print("done")
