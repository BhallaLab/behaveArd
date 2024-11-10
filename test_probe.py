import curses
import struct
import serial
import time
import numpy as np
import argparse


def fillProbes( args ):
    isProbe = innerFillProbes( args )
    while sum( isProbe ) != (args.numTrials // args.probeTrialSpacing):
        isProbe = innerFillProbes( args )
    return isProbe

def innerFillProbes( args ):
    lastProbe = 0
    # numProbes / numAvailSlots
    numProbes = args.numTrials // args.probeTrialSpacing
    newProbeProb = numProbes / (args.numTrials - numProbes * args.probeTrialMinSpacing )
    isProbe = np.zeros( args.numTrials, dtype=int )
    numActualProbes = 0
    for ii in range(args.numTrials):
        if ii > lastProbe+args.probeTrialMinSpacing:
            if np.random.rand() < newProbeProb and numActualProbes < numProbes:
                isProbe[ii] = 1
                lastProbe = ii
                numActualProbes += 1
    return isProbe

def main():
    ''' This program controls an arduino which performs precise timing for
    a mouse behavioural protocol. There is also an ncurses interface to see
    what is going on with the hardware events and the animal's movement.
    '''
    parser = argparse.ArgumentParser( description = 'behave.py: A program to control mouse behaviour on arduino.' )
    parser.add_argument('-p', '--protocol', type = str, help = "Optional: Specify which protocol of light, sound, multics or oddball. Default: sound.", default = "sound" )
    parser.add_argument('-n', '--numTrials', type = int, help = "Optional: How many trials to run. Default: 60.", default = 60 )
    parser.add_argument('-ps', '--probeTrialSpacing', type = int, help = "Optional: Mean spacing between as probe trials. Default: 10.", default = 10 )
    parser.add_argument('-pm', '--probeTrialMinSpacing', type = int, help = "Optional: Minimum number of trials between probe trials. Default: 6.", default = 6 )
    args = parser.parse_args()
    isProbe = fillProbes( args )
    print( "NUM PROBE = ", sum( isProbe ) )
    for idx, val in enumerate( isProbe ):
        if val:
            print( idx, val )

if __name__ == "__main__":
    main()

