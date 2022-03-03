"""
hist_fit_to_data.py
    
    Created/edited by Lewis Chan, 2021-03-23

    A combination of Histogram_Times.py and curve_fit_to_data.py.

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

import glob
import scipy
import scipy.optimize, scipy.special, scipy.stats
import numpy as np
import matplotlib.pyplot as plt
plt.rcParams.update({"font.size": 8, "figure.dpi": 200})

## Function to fit: 'x' is the independent variable(s), 'p' the parameter vector
#   Note:   These are just examples; normally you will write your own function.
#           A one line lambda function definition  can be used for very simple
#           functions, but using "def" always works.
#   Note:   "*p" unpacks p into its elements; needed for curvefit
def gaussian(x,*p) :
    # A gaussian peak with:
    #   Constant Background          : p[0]
    #   Peak height above background : p[1]
    #   Central value                : p[2]
    #   Standard deviation           : p[3]
    return p[0]+p[1]*np.exp(-1*(x-p[2])**2/(2*p[3]**2))
def lorentzian(x,*p) :
    # A lorentzian peak with:
    #   Constant Background          : p[0]
    #   Peak height above background : p[1]
    #   Central value                : p[2]
    #   Full Width at Half Maximum   : p[3]
    return p[0]+(p[1]/np.pi)/(1.0+((x-p[2])/p[3])**2)
def linear(x,*p) :
    # A linear fit with:
    #   Intercept                    : p[0]
    #   Slope                        : p[1]
    return p[0]+p[1]*x
def power(x,*p) :
    # A power law fit with:
    #   Normalization                : p[0]
    #   Offset                       : p[1]
    #   Constant                     : p[3]
    return p[0]*(x-p[1])**p[2]+p[3]
def exponential(x,*p):
    # An exponential fit with:
    #   Scaling factor               : p[0]
    #   Time constant                : p[1]
    #   Constant background          : p[2]
    return p[0]*np.exp(-x/p[1]) + p[2]

##########################################################################
### USER PARAMETERS

## Load data from file (Change name to your data file)
#   Data file is a simple text file, with columns of numbers.
#   The "columns" do not need to be aligned.

# Use Unix style wildcard matching for multiple files
# filelist = glob.glob('data/times_lc_liq_run4*')
# filelist = glob.glob('run4_75V/times_lc_NaI_run4*')
# filelist = glob.glob('run2_~76mV/times_lc_NaI_run2*')
# filelist = glob.glob('times_lc_NaI_run4*')
# filelist = glob.glob('run5_76mV/times_lc_NaI_run5*')
# filelist6 = glob.glob('run6_76mV/times_lc_NaI_run6*')
filelist = glob.glob('run9_76mV/times_lc_NaI_run9*')

# filelist.extend(filelist6)

## Choose function
func = exponential

## Initial guesses for fit parameters
#       Note: The comma after the last parameter is unnecessary unless
#               you only have one parameter.
p_guess = (2000, 2.2, 27)

## Plot settings
logscale = True
title = "Muon decay times from Liquid Scintillator Detector"
xlabel = "Separation between two pulses (µs)"
ylabel = "Counts"
saveplt = False
filename = "muon_liq_hist_prelim"

##########################################################################

ratio_cut = 20

# get rid of empty data files (which throw errors) and remove any events with 0 delay time
data_list = []
for f in filelist:
    try:
        data = np.loadtxt(f, usecols=5, skiprows=3)
        
        peak1 = np.loadtxt(f, usecols=7, skiprows=3) # [V] first peak
        peak2 = np.loadtxt(f, usecols=8, skiprows=3) # [V] second peak

        if len(np.shape(data)) != 0:
           zero_inds = np.where(data == 0)
           # zero_inds = np.where(data <= 0.32) # cut first bin
           
           data = np.delete(data,zero_inds)
           peak1 = np.delete(peak1,zero_inds)
           peak2 = np.delete(peak2,zero_inds)
           
           ratio_inds = np.where(peak1 / peak2 > ratio_cut)
           data = np.delete(data,ratio_inds)
           
           data_list.append(data)

    except TypeError:
        continue 

# decay_times = np.concatenate(list(np.loadtxt(f, usecols=5, skiprows=2) for f in filelist)) # [mu s]
decay_times = np.concatenate(list(data for data in data_list)) # [mu s]


# decay_times = decay_times[decay_times > 0.5] # ignore data less than 0.5 mu s seperation

# Current format
N_decays = len(decay_times)
hist_min, hist_max = 0, 12

## Histogram the selected data column
hist, bin_edges = np.histogram(
                decay_times,          # Selected data column
                # All the following parameters are optional
                bins      = 75,   #'auto' # number of histogram bins
                # Minimum and maximum of data to be plotted
                range     = (hist_min, hist_max),
                density   = False,    # normalize histogram to unity
                )
print(N_decays, "entries in histogram\n")

## Write histogram to file ("hist.txt"), if desired, e.g. for fitting.
#   The format is centre-of-bin position, width of bin, number of counts in bin.
bin_width     = (bin_edges[1]-bin_edges[0])
bin_positions = bin_edges[0:-1]+bin_width/2.0
#bin_widths    = len(hist)*[bin_width]
#np.savetxt("hist.txt", list(zip(bin_positions, bin_widths, hist)))

#hist = hist - np.mean(hist[bin_positions>10])
bin_positions = (temp:=bin_positions[hist>0])#[temp>1]
hist = (hist[hist>0])#[temp>1]

lifetime = 2.19698   # [mu s] Muon lifetime
x_func = np.arange(hist_min, hist_max, 0.05)
y_theoretical = 1/lifetime*np.exp(-x_func/lifetime)
y_sigma = np.sqrt(hist)


# Record initial function guess for later plotting
#   Create many finely spaced points for function plot
#           linspace(start,stop,num)
#               returns num evenly spaced samples over interval [start, stop]
initial_plot = func(x_func,*p_guess)

## Fit function to data
# This fits the function "func" to the data points (x, y_data) with y
#   uncertainties "y_sigma", and initial parameter values p0.
#   Note: Try replacing 1171 by 1170 and see what happens.
try:
    p, cov = scipy.optimize.curve_fit(
                func, bin_positions, hist, p0=p_guess, sigma=y_sigma,
                maxfev=100*(len(bin_positions)+1))
    #     Notes: maxfev is the maximum number of func evaluations tried; you
    #               can try increasing this value if the fit fails.
    #            If the program returns a good chi-squared but an infinite
    #               covariance and no parameter uncertainties, it may be
    #               because you have a redundant parameter;
    #               try fitting with a simpler function.
# Catch any fitting errors
except:
    p, cov = p_guess, None

# Calculate residuals (difference between data and fit)
for i in enumerate(hist):
    y_fit = func(bin_positions,*p)
    y_residual = hist - y_fit

# Calculate degrees of freedom of fit
dof = len(bin_positions) - len(p)

## Output results

print("******** RESULTS FROM FIT ******** (by hist_fit_to_data.py)")
print("Fit Function: ",func.__name__)
print("\nNumber of Data Points = {:7g}, Number of Parameters = {:1g}"\
      .format(len(bin_positions), len(p) ))

print("\nScipy Covariance Matrix : \n", cov)
chisq = None
try:
    # Calculate Chi-squared
    chisq = sum(((hist-func(bin_positions,*p))/y_sigma)**2)
    # WARNING : Scipy seems to use non-standard poorly documented notation for cov,
    #   which misleads many people. See "cov_x" on
    #   http://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.leastsq.html#scipy.optimize.leastsq
    #   (which underlies curve_fit) and also discussion at
    #   http://stackoverflow.com/questions/14854339/in-scipy-how-and-why-does-curve-fit-calculate-the-covariance-of-the-parameter-es.
    #   I think this agrees with @cdeil at http://nbviewer.ipython.org/5014170/.
    #   THANKS to Wes Watters <wwatters@wellesley.edu> for pointing this out to me (16 September 2013)
    #
    # Convert Scipy cov matrix to standard covariance matrix.
    cov = cov*dof/chisq
    print("Correlation Matrix :")
    for i,row in enumerate(cov):
        for j in range(len(p)) :
            print("{:10f}".format(cov[i,j]/np.sqrt(cov[i,i]*cov[j,j])),end="")
        print()
    print("\nEstimated parameters and uncertainties (with initial guesses)")
#  Note: If the fit is poor, i.e. chisq/dof is large, the uncertainties
#   are scaled up. If the fit is too good, i.e. chisq/dof << 1, it suggests
#   that the uncertainties have been overestimated, but the uncertainties
#   are not scaled down.
    for i in range(len(p)) :
        print ("   p[{:d}] = {:10.5f} +/- {:10.5f}      ({:10.5f})"
                   .format(i,p[i],cov[i,i]**0.5*max(1,np.sqrt(chisq/dof)),
                       p_guess[i]))

    cdf = scipy.special.chdtrc(dof,chisq)
    print("\nChi-Squared/dof = {:10.5f}, CDF = {:10.5f}%"\
        .format(chisq/dof, 100.*cdf))
    if cdf < 0.05 :
        print("\nNOTE: This does not appear to be a great fit, so the")
        print("      parameter uncertainties may be underestimated.")
    elif cdf > 0.95 :
        print("\nNOTE: This fit seems better than expected, so the")
        print("      data uncertainties may have been overestimated.")


# If cov has not been calculated because of a bad fit, the above block
#   will cause a python TypeError which is caught by this try-except structure.
except TypeError:
    print("**** BAD FIT ****")
    print("Parameters were: ",p)
    # Calculate Chi-squared for current parameters
    chisq = sum(((hist-func(bin_positions,*p))/y_sigma)**2)
    print("Chi-Squared/dof for these parameter values = {:10.5f}, CDF = {:10.5f}%"\
        .format(chisq/dof, 100.*float(scipy.special.chdtrc(dof,chisq))))
    print("Uncertainties not calculated.")
    print()
    print("Try a different initial guess for the fit parameters.")
    print("Or if these parameters appear close to a good fit, try giving")
    print("    the fitting program more time by increasing the value of maxfev.")
    chisq = None


## Plot

fig = plt.figure()

fit = fig.add_subplot(311)
fit.set_xticklabels( () )
fit.plot(bin_positions, hist, ".r", label="Muon decay data")
fit.plot(np.sort(x_func), func(np.sort(x_func),*p), "-C0", label="Curve fit ({})".format(func.__name__))
#   draw starting guess as dashed green line ('r-')
#fit.plot(x_func, initial_plot, 'g-', label="Start", linestyle="--")
# Add error bars on data as red crosses.
fit.errorbar(bin_positions, hist, yerr=y_sigma, fmt='r|')

if logscale:
    fit.set_yscale("log") # "linear"
else:
    fit.set_ylim(bottom=0)
fit.set_xlim(0, 12.1)

# Plot and axis titles
fig.suptitle("Figure 1", weight='bold')
fit.set_title(title)
fit.set_ylabel(ylabel)

#fit.plot(x_func, y_theoretical, "--C2", label="2.19698 µs decay curve")

# A legend is optional, but is useful if more than one set of data plotted.
fit.legend()

# separate plot to show residuals
residuals = fig.add_subplot(312)
residuals.errorbar(bin_positions, y_residual, yerr=y_sigma, fmt='r+', label="Residuals")
# make sure residual plot has same x axis as fit plot
residuals.set_xlim(fit.get_xlim())
residuals.axhline(y=0) # draw horizontal line at 0 on vertical axis

# Label axes
#fig.text(0.04, 0.63, ylabel, va='center', rotation='vertical')
residuals.set_xlabel(xlabel)

# These data look better if 'plain', not scientific, notation is used,
#   and if the tick labels are not offset by a constant (as is done by default).
#   Note: This only works for matplotlib version 1.0 and newer, so it is
#           enclosed in a "try" to avoid errors.
try:
    residuals.ticklabel_format(style='plain', useOffset=False, axis='x')
except: pass

# print selected information in empty 3rd plot row
try:
    fig.text(0.05,0.22,"Converged with ChiSq = " + str(chisq) + ", DOF = " +
        str(dof) + ", CDF = " + str(100*scipy.special.chdtrc(dof,chisq))+"%"
        +'\nRatio cut at: {}'.format(ratio_cut))
    for i, value in enumerate(p):
        plt.figtext(0.08,0.16-i*0.03, "p["+str(i)+"]" + " = " +
                   str(p[i]).ljust(18) + " +/- " +
                   str(np.sqrt(cov[i,i])*max(1,np.sqrt(chisq/dof))),
                   fontdict=None)
        # Note: Including family="Monospace" in the above figtext call will
        #       produce nicer looking output, but can cause problems with
        #       some older python installations.
except TypeError:
    fig.text(0.05,0.25,"BAD FIT.  Guess again.")

# Display data plot in terminal
plt.show()
# Save plot as a graphic file, if desired.
if saveplt == True:
    fig.savefig(f"{filename}.pdf", dpi=300)

##### End hist_fit_to_data

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
