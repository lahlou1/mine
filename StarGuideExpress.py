from time import mktime
from datetime import datetime
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui, QtCore, QtWidgets
import numpy as np

app = QtWidgets.QApplication([])

win = pg.GraphicsLayoutWidget(show=True)
plot1 = win.addPlot()
win.nextRow()
plot2 = win.addPlot()

plot1.addLegend()
plot2.addLegend()

curve1_x = plot1.plot(pen='r', name = 'cam1 x')
curve1_y = plot1.plot(pen='w', name = 'cam1 y')
curve2_x = plot2.plot(pen='r', name = 'cam2 x')
curve2_y = plot2.plot(pen='w',  name = 'cam2 y')
axis = pg.DateAxisItem()
plot1.setAxisItems({'bottom': axis})
plot2.setAxisItems({'bottom': pg.DateAxisItem()})


plot1.setLabel('left', "CAM1 dPOS [um]")
plot2.setLabel('left', "CAM2 dPOS [um]")


def update():
    d = np.load('positions.npz', allow_pickle=True)
    x, c, t1, t2 = d['times'][-100000::10], d['centroids'][-100000::10], d['targets'][0], d['targets'][1]
    c =  np.array(c)

    # x = [datetime for t in x]
    x = [mktime(dt.timetuple()) for dt in x]
    curve1_x.setData((c[:,0,0]-t1[1])*5, x=x)
    curve1_y.setData((c[:,0,1]-t1[0])*5, x=x)
    curve2_x.setData((c[:,1,0]-t2[1])*5, x=x)
    curve2_y.setData((c[:,1,1]-t2[0])*5, x=x)
    

timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(1000)

if __name__ == '__main__':
    app.exec_()
