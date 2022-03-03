# -*- coding: utf-8 -*-
"""
Created on Tue Mar  5 11:01:42 2019

@author: student
"""

# -*- coding: utf-8 -*-
"""
Created on Wed Jun  6 11:16:51 2018

@author: davidbailey
@updatedby: Capstone Group PhySol - Apurv Bharadwaj, Yvette de Sereville, David 
Kivlichan and Luke Licursi 

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

      
import visa
import time, datetime
import numpy
import os 

resources = visa.ResourceManager('@ni')
# Siglent 1104 Oscilloscope
scope = resources.open_resource('USB0::0xF4EC::0xEE38::SDSMMDBX2R0801::INSTR')
scope.write("WFSU SP,0,NP,0,FP,0")
print("Waveform READ settings :",scope.query('WFSU?'), end="")



def delayFinder(dataset, threshold, sara):
   "This finds the delay for points below a certain threshhold, based on a sampling rate"
   passed_threshold    = numpy.where(dataset < threshold)
   passed_threshold = passed_threshold[0]
   for i in (numpy.arange(len(passed_threshold)-1)):
       difference = passed_threshold[i+1] - passed_threshold[i]
       if(difference > 0):
           return (float(passed_threshold[i+1] - passed_threshold[0])) #/sara)
   return 0

OldDataSum1 = 9e99
CurrentDataSum1 = OldDataSum1


info_str = "_lc_NaI_run1_50mV" #"_lc_liq_run4"
if os.path.exists("pulses"+info_str+".txt"):
    info_str += '_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')


data = []
event_number=0

pulses = open("pulses"+info_str+".txt", "wb")
tdcs   = open("times"+info_str+".txt", "w")

trigger_times = []
pulse_sizes   = []

#Set file saving to USB

cwd = os.getcwd()

channel1 = open(os.path.join(cwd,"channel1_delays"+info_str+".txt"), "w")
log1 = open(os.path.join(cwd,"channel1_logs"+info_str+".txt"), "w")
log2 = open(os.path.join(cwd,"channel2_logs"+info_str+".txt"), "w")
log3 = open(os.path.join(cwd,"channel3_logs"+info_str+".txt"), "w")
log4 = open(os.path.join(cwd,"channel4_logs"+info_str+".txt"), "w")

# channel1 = open(os.path.join('T:',"channel1_delays.txt"), "w")
# log1 = open(os.path.join('T:',"channel1_logs.txt"), "w")
# log2 = open(os.path.join('T:',"channel2_logs.txt"), "w")
# log3 = open(os.path.join('T:',"channel3_logs.txt"), "w")
# log4 = open(os.path.join('T:',"channel4_logs.txt"), "w")

# Set parameters for data taking
maximum_run_time         =  66*60*60 #seconds
maximum_number_of_events = maximum_run_time/10 
threshold_count          = -10

# Default timeout is 2000 ms, which is too long, so make shorter
scope.timeout = 60000 #60000 #500 # in milliseconds

# Print settings read from scope
# Channel 1
#==============================================================================
# print(scope.query("SARA?"))     # Sampling Rate
# print(scope.query("SANU? C1"))  # Sample size for channel 1
# print(scope.query("TDIV?"))     # Time base
# print(scope.query("TRDL?"))     # Time delay
# #print(scope.query("TRSE?"))     # Trigger Condition, e.g. Interval
# #print(scope.query("C1:TRLV?"))  # Trigger Level
# print(scope.query("TRMD?"))     # Trigger Sweep Mode
# print(scope.query("TRPA?"))     # Trigger Pattern
# #print(scope.query("C1:TRCP?"))  # Trigger Coupling for channel 1
# print(scope.query("C1:TRLV2?")) # Trigger Level 2

Sara = scope.query("SARA?")
Sara = float(Sara[5:13]) #sampling rate (points / s)
#==============================================================================
#scope.write("C2:TRA ON")  # Make sure Channel 2 trace is on to avoid bug
# Arm scop to trigger on a single event
scope.write('TRMD SINGLE')
scope.write("ARM")


start_time1 = time.time()


date_label = ("Data taking started at {0:17.4f} seconds (".format( time.time())
                + str(datetime.datetime.now())+")")

print(date_label)

tdcs.write(date_label+"\n" )
print("Event     Delta Time    Absolute Time    min  max  "+
      "trigger  pulse size")
channel1.write("Event     Delta Time    Absolute Time   min  max "+
      "Trigger pulse size\n")

while event_number < maximum_number_of_events :
    # Make one acquisition for channel 1 
    try :
        scope.write("SAST?")
        status=scope.read()
        if status[5:9]!="Stop" :
            continue
#read channel 1
        scope.write("C1:WF? DAT2")
        trace1              = scope.read_raw()
        wave1               = trace1[21:-2] # Strip "\n\n" from end, the waveform
        # adc1                = numpy.fromstring(wave1, dtype = 'int8')
        adc1                = numpy.frombuffer(wave1, dtype='int8')
#read channel 2         
        scope.write("C2:WF? DAT2")
        trace2             = scope.read_raw()
        wave2               = trace2[21:-2] # Strip "\n\n" from end, the waveform
        # adc2                = numpy.fromstring(wave2, dtype = 'int8')
        adc2                = numpy.frombuffer(wave2, dtype='int8')
#read channel 3
        scope.write("C3:WF? DAT2")
        trace3             = scope.read_raw()
        wave3               = trace3[21:-2] # Strip "\n\n" from end, the waveform
        # adc3                = numpy.fromstring(wave1, dtype = 'int8')
        adc3                = numpy.frombuffer(wave3, dtype='int8')
#read channel 4
        scope.write("C4:WF? DAT2")
        trace4             = scope.read_raw()
        wave4               = trace4[21:-2] # Strip "\n\n" from end, the waveform
        # adc4                = numpy.fromstring(wave1, dtype = 'int8')
        adc4                = numpy.frombuffer(wave4, dtype='int8')
        
        CurrentDataSum1      = sum(adc1)
        
        #if CurrentDataSum1 != OldDataSum1 :
        trigger_time1 = delayFinder(adc1, threshold_count, Sara)
        
        event_absolute_time1 = time.time()
        event_delta_time1 = event_absolute_time1 - start_time1
        # For now, pulse size is just total adc counts, but should 
        #   probably fit using Marrone 2002 parameterization
        #   (https://doi.org/10.1016/S0168-9002(02)01063-X)
        pulse_size1          = CurrentDataSum1
        trigger_times.append(trigger_time1)
        pulse_sizes.append(pulse_size1)
        pulses.write( wave1 )
        pulses.flush()

        
        tdc_string1 = ( ('{0: >5} {1:14.4f} {2:17.4f} {3:4d} {4:4d} {5:12.20f}'+
                       ' {6:6d}').
                          format(event_number, event_delta_time1,
                                 event_absolute_time1, min(adc1), max(adc1),
                                 trigger_time1, pulse_size1 ))
        tdc_string = ()
        print(tdc_string1)

        channel1.write(tdc_string1+"\n")
        
        for item in adc1:
            log1.write("%s " % item)
        log1.write("\n")
        log1.flush()
        
        for item in adc2:
            log2.write("%s " % item)
        log2.write("\n")
        log2.flush()

        for item in adc3:
            log3.write("%s " % item)
        log3.write("\n")
        log3.flush()
        
        for item in adc4:
            log4.write("%s " % item)
        log4.write("\n")
        log4.flush()

        tdcs.write(tdc_string1+"\n" )
        tdcs.flush()
        
        OldDataSum1 = CurrentDataSum1
        
        event_number = event_number+1
        
    except :
        print("Readout Error!",status[5:])
        time.sleep(0.1)
    if (time.time()-start_time1) > maximum_run_time :
        print("Exceeded Maximum Time of ", maximum_run_time, "seconds")
        break
    else :
        scope.write('TRMD SINGLE')
        scope.write("ARM")
        scope.write("C2:TRA ON")
        time.sleep(0.2)
acquisition_time = time.time()-start_time1
print("Finished Data Acquisition after",acquisition_time,"seconds")
print("Events recorded :",event_number)
print(trigger_times)
channel1.close()
log1.close()
log2.close()
log3.close()
log4.close()



