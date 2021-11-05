#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Edited 2021-03-23 by Lewis Chan

Created on Wed Jun  6 11:16:51 2018

@author: davidbailey

Test program to read history frames from Siglent SDS1204X-E Oscilloscope
For complete list of commands, see
https://www.siglentamerica.com/wp-content/uploads/dlm_uploads/2017/10/Programming-Guide-1.pdf

TROUBLESHOOTING NOTES:
    - Use smallest Mem Depth to avoid Read Errors
    – Interval trigger seems to stop working if Channel 2 is turned off, so
         code below forces it to be on.
    – Unplug and replug USB cable if IO Error occurs.
    - Turn scope on and off if still problems.
"""

import os
import visa
import time, datetime
import numpy
import scipy.signal
#import matplotlib.pyplot as plt

# Set parameters for data taking
maximum_run_time         = 7*24*60*60 # 7*24*60*60 #60      # seconds
maximum_number_of_events = 7*24*60*600 #100000 #100
#threshold_count          = 50

# Choose files to save data to
info_str = "_lc_NaI_run9" #"_lc_liq_run4"
if os.path.exists("pulses"+info_str+".txt"):
    info_str += '_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

trigger_times = []
#pulse_sizes   = []
#OldDataSum = 9e99
#CurrentDataSum = OldDataSum
event_number = 0

# Initialize device and other parameters
resources = visa.ResourceManager('@ni')
# Siglent 1104 Oscilloscope
scope = resources.open_resource('USB0::0xF4EC::0xEE38::SDSMMDBX2R0801::INSTR')
scope.write("WFSU SP,0,NP,0,FP,0")
print("Waveform READ settings :",scope.query('WFSU?'), end="")

# Default timeout is 2000 ms
scope.timeout = 20000 # in milliseconds

def bits_to_volts(bits):
    return bits*(volts_per_div/25)-volt_offset

# Print settings read from scope
print(scope.query("SARA?"))     # Sampling Rate
print(scope.query("SANU? C1"))  # Sample size for channel 1
print(scope.query("TDIV?"))     # Time base
print(scope.query("TRDL?"))     # Time delay
print(scope.query("TRSE?"))     # Trigger Condition, e.g. Interval
#print(scope.query("TRMD?"))     # Trigger Sweep Mode
#print(scope.query("TRPA?"))     # Trigger Pattern
print(scope.query("C1:TRLV?"))  # Trigger Level
#print(scope.query("C1:TRLV2?")) # Trigger Level 2
print(scope.query("C1:TRCP?"))  # Trigger Coupling for channel 1

volts_per_div = float(scope.query("C1:VDIV?")[8:-2])
volt_offset = float(scope.query("C1:OFST?")[8:-2])
sample_rate = float(scope.query("SARA?")[5:-5])

#trig_level = float(scope.query("C1:TRLV2?")[8:-2])
#t_per_div = float(scope.query("TDIV?")[5:-2])     # Time base
#t_offset = float(scope.query("TRIG_DELAY?")[5:-2])                    

#xaxis = 1E6 * numpy.arange(-t_per_div*7-t_offset, t_per_div*7-t_offset, 1/sample_rate) # us

#%%

scope.write("C2:TRA ON")  # Make sure Channel 2 trace is on to avoid bug
scope.write("C1:TRA ON")
# Arm scope to trigger on a single event
scope.write('TRMD SINGLE')
#scope.write("ARM")

pulses = open("pulses"+info_str+".txt", "wb") # "pulses.txt"
tdcs   = open("times"+info_str+".txt", "w") # "times.txt"

start_time = time.time()
date_label = ("Data taking started at {0:17.4f} seconds (".format( time.time())
                + str(datetime.datetime.now())+")")
print(date_label)
tdcs.write(date_label+"\n" )

scope_settings = "volts / div = {} V / div \t volts offset = {} V \t sample rate = {} Hz \n".format(volts_per_div, volt_offset, sample_rate)
tdcs.write(scope_settings)

header = ("Event     Delta Time     Absolute Time   min[V]   max[V]   "+
      "Delay[us]   pulse size  peak1 min [V]   peak2 min [V]")
print(header)
tdcs.write(header+"\n" )

while True:
    # Make one acquisition
    try:
        scope.write("SAST?") #return the acquisition status of the scope
        status=scope.read()
        if status[5:9]!="Stop" :
            continue #go back to beginning of while loop
        scope.write("C1:WF? DAT2")
        trace1              = scope.read_raw()
        event_absolute_time = time.time()
        
        wave1               = trace1[21:-2] # Strip "\n\n" from end
        adc1                = numpy.frombuffer(wave1, dtype='int8')
        volts1 = bits_to_volts(adc1)
        #numpy.savetxt('sample_NaI_pulse.txt', numpy.column_stack((xaxis, volts1)))
        CurrentDataSum      = sum(volts1)
        #CurrentDataSum      = sum(adc1)
        #if CurrentDataSum != OldDataSum :
        event_delta_time    = event_absolute_time - start_time
        #passed_threshold_indices    = numpy.nonzero(volts1 <= trig_level)[0]
        #if len(passed_threshold_indices>0):
        #    trigger_time        = 1/sample_rate*(passed_threshold_indices[-1]-passed_threshold_indices[0])
        #else:
        #    print(passed_threshold_indices)
        #    trigger_time = 0
        
        # Adjust peak prominence to be just below desired oscill. threshold!
        peaks = scipy.signal.find_peaks(-volts1, prominence=0.019, # V
                                        distance=int(0.2E-6*sample_rate))[0] # s
        
        if len(peaks)>1:
            trigger_time = 1/sample_rate*(peaks[-1] - peaks[0]) * 1e6 # us
            V_pulse2 = volts1[peaks[1]] # voltage of last peak
    
            # print('last min '+volts1[peaks[-1]]+'\n')
            # tdcs.write('last min '+volts1[peaks[-1]]+'\n')
    
        else:
            trigger_time = 0
            V_pulse1 = 0
            V_pulse2 = 0
    
        if len(peaks) != 0:
            V_pulse1 = volts1[peaks[0]] # voltage of first peak
        
        
        # For now, pulse size is just total adc counts, but should 
        #   probably fit using Marrone 2002 parameterization
        #   (https://doi.org/10.1016/S0168-9002(02)01063-X)
        pulse_size          = CurrentDataSum
        trigger_times.append(trigger_time)
        #pulse_sizes.append(pulse_size)
        pulses.write( wave1 )
        pulses.flush()
        tdc_string = ( ('{0: >5} {1:14.4f} {2:17.4f} {3:8.4f} {4:8.4f} {5:11.4f}'+
                       ' {6:12.4f} {7:12.4f} {8:12.4f}').
                          format(event_number, event_delta_time,
                                 event_absolute_time, min(volts1), max(volts1),
                                 trigger_time, pulse_size, V_pulse1, V_pulse2  ))
        print(tdc_string)
        tdcs.write(tdc_string+"\n" )
        tdcs.flush()
        event_number += 1
        #OldDataSum = CurrentDataSum
    except Exception as e:
        print(e)
        print("Readout Error!", status[5:])
        time.sleep(0.2)
        break
    
    if (time.time()-start_time) > maximum_run_time:
        print("Exceeded Maximum Time of ", maximum_run_time, "seconds")
        break
    elif event_number >= maximum_number_of_events:
        break
    else:
        #scope.write('TRMD SINGLE')
        scope.write("ARM")
        #scope.write("C2:TRA ON")
        time.sleep(0.2)

acquisition_time = time.time()-start_time
print("Finished Data Acquisition after", acquisition_time, "seconds")
print("Events recorded:", event_number)
print(trigger_times)

pulses.close()
tdcs.close()
