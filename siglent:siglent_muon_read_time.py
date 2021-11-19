#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun  6 11:16:51 2018

@author: davidbailey

Test program to read history frames from Siglent SDS1204X-E Oscilloscope
For complete list of commands, see
https://www.siglentamerica.com/wp-content/uploads/dlm_uploads/2017/10/Programming-Guide-1.pdf

TROUBLESHOOTING NOTES:
    - Use smallest Mem Depth to avoid Read Errors
    â€“ Interval trigger seems to stop working if Channel 2 is turned off, so
         code below forces it to be on.
    â€“ Unplug and replug USB cable if IO Error occurs.
    - Turn scope on and off if still problems.
"""

import visa
import time, datetime
from array import array
import numpy
from matplotlib import pyplot as plt



def min1_min2_indices(number_array):
    lst = []
    for i in range(len(number_array) - 1):
        if number_array[i - 1] > number_array[i] < number_array[i + 1] and number_array[i] < 60:
            lst.append(i)
    return lst

time_per_unit = 2      #in nano seconds

resources = visa.ResourceManager('@ni')
# Siglent 1104 Oscilloscope
scope = resources.open_resource('USB0::0xF4EC::0xEE38::SDSMMDBX2R0801::INSTR')
scope.write("WFSU SP,0,NP,0,FP,0")
print("Waveform READ settings :",scope.query('WFSU?'), end="")

OldDataSum = 9e99
CurrentDataSum = OldDataSum
data = []
event_number=0
pulses = open("pulses.txt", "wb")
tdcs   = open("times.txt", "w")
trigger_times = []
pulse_sizes   = []

# Set parameters for data taking
maximum_run_time         = 3600      # seconds
maximum_number_of_events = 9999
threshold_count          = 50

# Default timeout is 2000 ms, which is too long, so make shorter
scope.timeout = 500 # in milliseconds

# Print settings read from scope
print(scope.query("SARA?"))     # Sampling Rate
print(scope.query("SANU? C1"))  # Sample size for channel 1
print(scope.query("TDIV?"))     # Time base
print(scope.query("TRDL?"))     # Time delay
print(scope.query("TRSE?"))     # Trigger Condition, e.g. Interval
print(scope.query("C1:TRLV?"))  # Trigger Level
print(scope.query("TRMD?"))     # Trigger Sweep Mode
print(scope.query("TRPA?"))     # Trigger Pattern
print(scope.query("C1:TRCP?"))  # Trigger Coupling for channel 1
print(scope.query("C1:TRLV2?")) # Trigger Level 2

scope.write("C2:TRA ON")  # Make sure Channel 2 trace is on to avoid bug
# Arm scop to trigger on a single event
scope.write('TRMD SINGLE')
scope.write("ARM")

start_time = time.time()
date_label = ("Data taking started at {0:17.4f} seconds (".format( time.time())
                + str(datetime.datetime.now())+")")
print(date_label)
tdcs.write(date_label+"\n" )
print("Event     Delta Time    muon lifetime   min  my_trigger "+
      "trigger pulse size")
while event_number < maximum_number_of_events :
    # Make one acquisition
    try :
        scope.write("SAST?")
        status=scope.read()
        if status[5:9]!="Stop" :
            continue
        scope.write("C1:WF? DAT2")
        trace1              = scope.read_raw()
        wave1               = trace1[21:-2] # Strip "\n\n" from end
        adc1                = numpy.array(array('b',wave1).tolist())
        CurrentDataSum      = sum(adc1)
        peaks_indeces = min1_min2_indices(adc1)
        x_axis = numpy.arange(len(adc1[peaks_indeces[0]-5:peaks_indeces[0]+5]))
        plt.plot(x_axis, adc1[peaks_indeces[0]-5:peaks_indeces[0]+5])
        plt.savefig('run ' + str(event_number),dpi=300)
        plt.show()
        if CurrentDataSum != OldDataSum :
            passed_threshold    = numpy.nonzero(adc1 < threshold_count)
            event_absolute_time = time.time()
            time_between_peaks = time_per_unit*abs(peaks_indeces[0] - peaks_indeces[1])
            event_delta_time    = event_absolute_time - start_time
            trigger_time        = passed_threshold[0][0]
            # For now, pulse size is just total adc counts, but should 
            #   probably fit using Marrone 2002 parameterization
            #   (https://doi.org/10.1016/S0168-9002(02)01063-X)
            pulse_size          = CurrentDataSum
            trigger_times.append(trigger_time)
            pulse_sizes.append(pulse_size)
            pulses.write( wave1 )
            pulses.flush()
            tdc_string = ( ('{0: >5} {1:14.4f} {2:17.4f} {3:4d} {4:4d} {5:5d}'+
                           ' {6:6d}').
                              format(event_number, event_delta_time,
                                     time_between_peaks, min(adc1), peaks_indeces[0],
                                     trigger_time, pulse_size ))
            print(tdc_string)
            tdcs.write(tdc_string+"\n" )
            tdcs.flush()
            event_number = event_number+1
            OldDataSum = CurrentDataSum
    except :
        print("Readout Error!",status[5:])
        time.sleep(0.2)
    if (time.time()-start_time) > maximum_run_time :
        print("Exceeded Maximum Time of ", maximum_run_time, "seconds")
        break
    else :
        #scope.write('TRMD SINGLE')
        scope.write("ARM")
        #scope.write("C2:TRA ON")
        time.sleep(0.2)
acquisition_time = time.time()-start_time
print("Finished Data Acquisition after",acquisition_time,"seconds")
print("Events recorded :",event_number)
print(trigger_times)
