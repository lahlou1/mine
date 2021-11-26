"""
histogram_1D.py

    A simple example to histogram data from a file and output it.

    To histogram your own data, you need to change:
    (1) name of file containing the data ("hist_data.txt" in this example)
    (2) select the column containing the data to be histogrammed.
    (3) any desired optional parameters or labels.

    The program produces a histogram, which is also saved as a text file
    (e.g. for input to a fitting program) and as a png graphic.

    Copyright (c) 2013 University of Toronto
    Copyright (c) 2011-2017 University of Toronto
    Modifications:
        6 August 2017 by David Bailey
            Fixed made python 2.7+ and python 3+ compatible
    Original Version:   2 March  2013 by David Bailey
    Contact: David Bailey <dbailey@physics.utoronto.ca>
                            (http://www.physics.utoronto.ca/~dbailey)
    License: Released under the MIT License; the full terms are this license
                are appended to the end of this file, and are also available
                at http://www.opensource.org/licenses/mit-license.php.

    Note: The code is over-commented since it is is a pedagogical example for
    	students new to python and scipy.

"""
# Use python 3 consistent printing and unicode
from __future__ import print_function
from __future__ import unicode_literals

import numpy
from matplotlib import pyplot
from scipy.optimize import curve_fit



## Load data from file (Change name to your data file)
#   Data file is a simple text file, with columns of numbers.
#   The "columns" do not need to be aligned.

num_data_points = 60
columns = numpy.loadtxt("times.txt",unpack=True, skiprows=1, max_rows=num_data_points)  

print(columns[2][len(columns[2])-1])

time_division_size   = 2
frame_time_divisions = 14
frame_points         = 14000
print(columns[2])
zero_time = 23.65

# Current format
decay_times = columns[2]/1000  #micro seconds
N_decays = len(decay_times)
hist_min,hist_max = 0,25
num_bins = 30


## Histogram the selected data column
#    Only the column number is required, all other parameters are optional.
#       For all the pyplot.hist parameters and options, see
#           http://matplotlib.org/api/pyplot_api.html#matplotlib.pyplot.hist
bin_contents, bin_ends, patches = pyplot.hist(decay_times, bins=num_bins)

print(bin_contents, " entries in histogram")
print(bin_ends)

# Plot and axis titles (optional, but very strongly recommended)
pyplot.title("Muon Decay times from Old Liquid Scintillator Detector")
pyplot.title("Muon Decay times from NaI Detector")
pyplot.xlabel("Separation between two pulses (Âµs) ")
pyplot.ylabel("Entries")

## Write histogram to file ("hist.txt"), if desired, e.g. for fitting.
#   The format is centre-of-bin position, width of bin, number of counts in bin.
bin_width     = (bin_ends[1]-bin_ends[0])
bin_widths    = len(bin_contents)*[bin_width]
bin_positions = bin_ends[0:-1]+bin_width/2.0
numpy.savetxt("hist.txt", list(zip(bin_positions, bin_widths, bin_contents)))



def f(x, a, b, c):
    return a*numpy.exp(-b*x) + c

x = numpy.zeros(num_bins)
for i in range(num_bins):
    x[i] = bin_ends[i]



p_opt_1 , p_cov_1 = curve_fit(f, x, bin_contents)

print(p_opt_1)
print(p_cov_1)
truc = 1/p_opt_1[1]
error_truc = p_cov_1[1][1]*truc**2
print(truc)
print(error_truc)


lifetime = 2.197   # Muon lifetime
y=f(x, p_opt_1[0], p_opt_1[1], p_opt_1[2])
pyplot.plot(x,y,label=str(round(truc, 3)) + "±" + str(round(error_truc, 3)) + " Âµs decay curve")




pyplot.legend()
pyplot.gca().tick_params(which="both", right=True, top=True)




pyplot.savefig('histogram_demo',dpi=300)
pyplot.show()

##### End histogram_1D.py
"""
Full text of MIT License:

    Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""
