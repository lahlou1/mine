#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created 2021-03-30 by Lewis Chan

Only reading 3 channels for now since one of the scintillators is not working.

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

# Set parameters for data taking
maximum_run_time         = 10*60 #60      # seconds
maximum_number_of_events = 100000 #100
#threshold_count          = 50

# Choose files to save data to
info_str = "_angle_90"
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

def bits_to_volts(bits, volts_per_div, volt_offset):
    return bits*(volts_per_div/25)-volt_offset

# Print settings read from scope
print(scope.query("SARA?"))     # Sampling Rate
print(scope.query("SANU? C1"))  # Sample size for channel 1
print(scope.query("TDIV?"))     # Time base
print(scope.query("TRDL?"))     # Time delay
print(scope.query("TRSE?"))     # Trigger Condition, e.g. Interval
print(scope.query("TRMD?"))     # Trigger Sweep Mode
print(scope.query("TRPA?"))     # Trigger Pattern

volts_per_div1 = float(scope.query("C1:VDIV?")[8:-2])
volt_offset1 = float(scope.query("C1:OFST?")[8:-2])
volts_per_div2 = float(scope.query("C2:VDIV?")[8:-2])
volt_offset2 = float(scope.query("C2:OFST?")[8:-2])
volts_per_div3 = float(scope.query("C3:VDIV?")[8:-2])
volt_offset3 = float(scope.query("C3:OFST?")[8:-2])
#sample_rate = float(scope.query("SARA?")[5:-5])

#trig_level = float(scope.query("C1:TRLV2?")[8:-2])
#t_per_div = float(scope.query("TDIV?")[5:-2])     # Time base
#t_offset = float(scope.query("TRIG_DELAY?")[5:-2])                    

#xaxis = 1E6 * numpy.arange(-t_per_div*7-t_offset, t_per_div*7-t_offset, 1/sample_rate) # us

#%%

scope.write("C3:TRA ON")
scope.write("C2:TRA ON")
scope.write("C1:TRA ON")
# Arm scope to trigger on a single event
scope.write('TRMD SINGLE')
#scope.write("ARM")

tdcs   = open("times"+info_str+".txt", "w") # "times.txt"

start_time = time.time()
date_label = ("Data taking started at {0:17.4f} seconds (".format( time.time())
                + str(datetime.datetime.now())+")")
print(date_label)
tdcs.write(date_label+"\n" )
header = ("Event     Delta Time     Absolute Time   min[V]   max[V]   "+
      "pulse size")
print(header)
tdcs.write(header+"\n" )

while True:
    if (time.time()-start_time) > maximum_run_time:
        print("Exceeded Maximum Time of ", maximum_run_time, "seconds")
        break
    elif event_number >= maximum_number_of_events:
        break
    
    # Make one acquisition
    try:
        scope.write("SAST?") #return the acquisition status of the scope
        status=scope.read()
        if status[5:9]!="Stop" :
            continue #go back to beginning of while loop
        scope.write("C1:WF? DAT2")
        trace1              = scope.read_raw()
        event_absolute_time1 = time.time()
        scope.write("C2:WF? DAT2")
        trace2              = scope.read_raw()
        event_absolute_time2 = time.time()
        scope.write("C3:WF? DAT2")
        trace3              = scope.read_raw()
        event_absolute_time3 = time.time()
        
        wave1               = trace1[21:-2] # Strip "\n\n" from end
        adc1                = numpy.frombuffer(wave1, dtype='int8')
        volts1 = bits_to_volts(adc1, volts_per_div1, volt_offset1)
        wave2               = trace2[21:-2] # Strip "\n\n" from end
        adc2                = numpy.frombuffer(wave2, dtype='int8')
        volts2 = bits_to_volts(adc2, volts_per_div2, volt_offset2)
        wave3               = trace3[21:-2] # Strip "\n\n" from end
        adc3                = numpy.frombuffer(wave3, dtype='int8')
        volts3 = bits_to_volts(adc3, volts_per_div3, volt_offset3)
        
        #numpy.savetxt('sample_coincident.txt', numpy.column_stack((xaxis, volts1,
        #                                                           volts2, volts3)))
        CurrentDataSum1      = sum(volts1)
        CurrentDataSum2      = sum(volts2)
        CurrentDataSum3      = sum(volts3)
        
        event_delta_time1    = event_absolute_time1 - start_time
        event_delta_time2    = event_absolute_time2 - start_time
        event_delta_time3    = event_absolute_time3 - start_time
        
        # For now, pulse size is just total adc counts, but should 
        #   probably fit using Marrone 2002 parameterization
        #   (https://doi.org/10.1016/S0168-9002(02)01063-X)
        
        tdc_string1 = ( ('{0: >5} {1:14.4f} {2:17.4f} {3:8.4f} {4:8.4f}'+
                       ' {5:12.4f}').
                          format(event_number, event_delta_time1,
                                 event_absolute_time1, min(volts1), max(volts1),
                                 CurrentDataSum1    ))
        tdc_string2 = ( ('{0: >5} {1:14.4f} {2:17.4f} {3:8.4f} {4:8.4f}'+
                       ' {5:12.4f}').
                          format(event_number, event_delta_time2,
                                 event_absolute_time2, min(volts2), max(volts2),
                                 CurrentDataSum2    ))
        tdc_string3 = ( ('{0: >5} {1:14.4f} {2:17.4f} {3:8.4f} {4:8.4f}'+
                       ' {5:12.4f}').
                          format(event_number, event_delta_time3,
                                 event_absolute_time3, min(volts3), max(volts3),
                                 CurrentDataSum3    ))
        print(tdc_string1)
        print(tdc_string2)
        print(tdc_string3)
        tdcs.write(tdc_string1+"\n" )
        tdcs.write(tdc_string2+"\n" )
        tdcs.write(tdc_string3+"\n" )
        tdcs.flush()
        event_number += 1
    except Exception as e:
        print(e)
        print("Readout Error!", status[5:])
        time.sleep(0.2)
        break
    
    scope.write("ARM")
    time.sleep(0.2)

acquisition_time = time.time()-start_time
print("Finished Data Acquisition after", acquisition_time, "seconds")
print("Events recorded:", event_number)

tdcs.close()
