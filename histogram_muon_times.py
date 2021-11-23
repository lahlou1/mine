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

## Load data from file (Change name to your data file)
#   Data file is a simple text file, with columns of numbers.
#   The "columns" do not need to be aligned.
columns = numpy.loadtxt("times.txt",unpack=True, skiprows=1)     # Test

time_division_size   = 2
frame_time_divisions = 14
frame_points         = 14000
print(columns[5])
print(columns[1])
zero_time = 23.65

# Current format
decay_times = zero_time-columns[5]*time_division_size*frame_time_divisions/frame_points
N_decays = len(decay_times)
hist_min,hist_max = 0,25

## Histogram the selected data column
#    Only the column number is required, all other parameters are optional.
#       For all the pyplot.hist parameters and options, see
#           http://matplotlib.org/api/pyplot_api.html#matplotlib.pyplot.hist
bin_contents, bin_ends, patches = pyplot.hist(
                decay_times,          # Selected data column
                # All the following parameters are optional
                bins      = 50,      # number of hisogram bins
                # Minimum and maximum of data to be plotted
                range     = (hist_min,hist_max),
                label     = "muon decay data", # label for this data
                normed    = False,   # normalize histogram to unity
                log       = True,    # Choose if y log axis
                histtype  = "bar",   # Type of histogram
                facecolor = "green", # bar colour
                edgecolor = "blue",  # bar border colour
                linewidth = 1,       # bar border width
                alpha     = 0.8,     # bar transparency
                )

print(sum(bin_contents), " entries in histogram")

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

lifetime = 2.197   # Muon lifetime
x=numpy.arange(hist_min,0.5*hist_max,0.1)
y=bin_contents[0]*numpy.exp(-x/lifetime)
pyplot.plot(x,y,label="2.197 Âµs decay curve")

# A legend is optional, but is useful is more than one set of data plotted.
pyplot.legend()
pyplot.gca().tick_params(which="both", right=True, top=True)

# Save plot as a graphic file, if desired.
pyplot.savefig('histogram_demo',dpi=300)
# Display data plot in terminal
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
