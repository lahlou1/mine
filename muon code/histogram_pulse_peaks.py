# -*- coding: utf-8 -*-
"""
Created on Fri Oct  8 10:40:41 2021

@author: student
"""

import numpy as np
import glob
import matplotlib.pyplot as plt
import scipy.signal
import os


run_num = 9
dir_str = "run{}_76mV".format(run_num)
info_str = "lc_NaI_run{}".format(run_num)
filelist = glob.glob('{}/times_{}*'.format(dir_str, info_str))
# filelist = glob.glob('run5_76mV/times_lc_NaI_run5*')
# filelist = glob.glob('times_lc_NaI_run4*')

#------------------------------------------------------------------------------
# Plot ratio of first to second (last) peak in a run


data_list = []
data_list1 = []
data_list2 = []

for f in filelist:
    try:
        data1 = np.loadtxt(f, usecols=7, skiprows=3) # [V] first peak
        data2 = np.loadtxt(f, usecols=8, skiprows=3) # [V] second peak


        if len(np.shape(data1)) != 0:
            if len(np.shape(data2)) != 0:
                zero_inds = np.where(data2 == 0)

                data1 = np.delete(data1,zero_inds)
                data2 = np.delete(data2,zero_inds)

                #print(d)
                # data_list.append(- data1 / data2)
                data_list1.append(data1)
                data_list2.append(data2)

    except TypeError:
        continue 
    

    
peak_V1 = -np.concatenate(list(np.loadtxt(f, usecols=6, skiprows=2) for f in filelist)) # [V] first peak
peak_V2 = -np.concatenate(list(np.loadtxt(f, usecols=7, skiprows=2) for f in filelist)) # [V] second peak 
peak_V = -np.concatenate(list(data for data in data_list)) # [V] second peak 
peak_V1 = np.concatenate(list(data for data in data_list1)) # [V] second peak 
peak_V2 = np.concatenate(list(data for data in data_list2)) # [V] second peak 

# peak_V = peak_V[peak_V > 0]

hist, bin_edges = np.histogram(peak_V1 / peak_V2,bins=75)

bin_width     = (bin_edges[1]-bin_edges[0])
bin_positions = bin_edges[0:-1]+bin_width/2.0


hist1, bin_edges1 = np.histogram(peak_V1,bins=75)

bin_width1     = (bin_edges[1]-bin_edges[0])
bin_positions1 = bin_edges[0:-1]+bin_width/2.0


hist2, bin_edges2 = np.histogram(peak_V2,bins=75)

bin_width2     = (bin_edges[1]-bin_edges[0])
bin_positions2 = bin_edges[0:-1]+bin_width/2.0


fig, ax = plt.subplots(2,figsize=(8,5))

# fig = plt.figure()
# ax = fig.add_subplot(311)

# ax.set_title("Pulse Peak Distribution for run"+filelist[0][3])
# ax.set_xlabel("Pulse Peak [V]")
ax[0].set_title("First peak : Last peak Amplitude")
ax[0].set_xlabel("Ratio")

ax[0].bar(bin_positions, hist, label="")

ax[0].semilogy()

ax[1].set_title("First peak and second peak amplitude")
ax[1].set_xlabel("voltage [mV]")

ax[1].plot(bin_positions1, hist1, label="first peak")
ax[1].plot(bin_positions2, hist2, label="second peak")

ax[1].semilogy()

ax[1].legend()
plt.show()



#------------------------------------------------------------------------------
# Plot Traces and found peaks for individual events


volts_per_div = 0.100 #[V / div]
volt_offset = - 0.316 #[V]
# sara = 500000000 #[Hz]
sara = 7000 / (14 * 1e-6) # [Hz] samples per trace / trace delta time (1 mu s / div)


file_num = 0

event_num = np.loadtxt(filelist[file_num], usecols=0, skiprows=3) # event number
delay = np.loadtxt(filelist[file_num], usecols=5, skiprows=3) # delay time

bins = (0.64,0.80)
# bins = (0.16,0.32)

upper = set(np.where(delay > bins[0])[0])
lower = set(np.where(delay < bins[1])[0])

bin_inds = list(upper.intersection(lower))

event = bin_inds[0]

# abs_time = np.loadtxt(filelist[0], usecols=2, skiprows=3)

# del_time = np.loadtxt(filelist[0], usecols=1, skiprows=3)

# [print((abs_time[i+1] - abs_time[i])) for i in range(100)]
# print("del time are ")

# ev_time_del = [(del_time[i+1] - del_time[i]) for i in range(100)]
# ev_time_abs = [(abs_time[i+1] - abs_time[i]) for i in range(100)]

# [print((del_time[i+1] - del_time[i]) == (abs_time[i+2] - abs_time[i+1])) for i in range(100)]


start_ind = 7000 * event
stop_ind = start_ind + 7000

# start_ind = int((abs_time[event] - abs_time[0]) * sara * 1e-6)
# stop_ind = int((abs_time[event+1] - abs_time[0]) * sara * 1e-6)
# 
def bits_to_volts(bits):
    return bits*(volts_per_div/25)-volt_offset

pulselist = glob.glob('{}/pulses_{}*'.format(dir_str, info_str))
# pulselist = glob.glob('{}/channel2_logs.txt'.format(os.getcwd(), info_str))

pulses = open(pulselist[file_num],'rb')
wave1 = pulses.read()
pulses.close()

adc1 = np.frombuffer(wave1, dtype='int8')
adc1 = adc1[start_ind:stop_ind]

volts = bits_to_volts(adc1)


peaks = scipy.signal.find_peaks(-volts, prominence=0.019, # V
                                        distance=int(0.2E-6*sara))[0] # s

time = np.arange(len(volts)) / sara

fig, ax = plt.subplots(figsize=(8,5))

ax.plot(time ,volts,label='pulse trace',lw=0,marker='.')

if len(peaks) != 0:
    ax.scatter(np.array([peaks[0],peaks[-1]]) / sara,[volts[peaks[0]], volts[peaks[-1]]],c='r',label='found peak')

ax.set_title('Pulse Trace and Found Peaks - Event {}'.format(event))
ax.set_xlabel("Time [s]")
ax.set_ylabel("Voltage [V]")

plt.legend()
plt.show()



