import sys
import time
import matplotlib.animation as animation
import numpy as np
import pandas as pd
import serial.tools.list_ports

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThreadPool
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import QSizePolicy
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from libs import SerialPort
from libs import AnalysisCollection
from libs import Deque
from libs import WorkerThreading
from libs import Logger

class PlotCanvas(FigureCanvas):
    def __init__(self, *args, **kwargs):
        self.ani = None
        self.serial = None
        self.animation_end = False
        self.write = False
        self.addition_analysis = False
        self.is_plotting = False
        self.add_data_1 = False
        self.add_data_2 = False
        self.add_data_3 = False
        self.add_data_4 = False
        self.current_channel = 'chan1'

        self.scale_factor = float(2.048/32784)

        self.current_time = 0
        self.time_iter = self.run_time()
        self.analysis_function = 'null'

        self.analysis = AnalysisCollection()
        self.avg_data = Deque(np.zeros(100))
        self.stdev_data = Deque(np.zeros(100))
        self.ydata_chan1 = Deque(np.zeros(100))
        self.ydata_chan2 = Deque(np.zeros(100))
        self.ydata_chan3 = Deque(np.zeros(100))
        self.ydata_chan4 = Deque(np.zeros(100))
        self.tdata = Deque(np.arange(0, 100))
        self.fig = Figure(figsize=(kwargs['width'], kwargs['height']), dpi=120)
        self.axes_top = self.fig.add_subplot(211, autoscaley_on=True)
        self.axes_bot = self.fig.add_subplot(212, autoscaley_on=True)

        FigureCanvas.__init__(self, self.fig)
        FigureCanvas.setSizePolicy(self, QSizePolicy.Expanding, QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

        self.lines = Line2D(self.tdata.to_numpy(),
                            self.get_chan('chan1').to_numpy(),
                            color='xkcd:sky blue',
                            marker='o',
                            linewidth=0)
        self.axes_top.add_line(self.lines)
        self.axes_top.set_ylim(0, 2.10)
        self.axes_top.set_xlim(0, 100)
        self.axes_top.grid(True)

        self.avg_lines = Line2D(self.tdata.to_numpy(),
                                self.avg_data.to_numpy(),
                                color='xkcd:teal',
                                marker='o',
                                linewidth=0)
        self.axes_bot.add_line(self.avg_lines)
        self.axes_bot.set_ylim(0, 2.1)
        self.axes_bot.set_xlim(0, 100)

        self.axes_bot.grid(True)

        self.analysis_function_dispatcher = {'rolling-average': self._analysis_rolling_average,
                                             'auto_correlation': self._auto_correlation,
                                             'null': self.none}

        self.draw()

        self.threadpool = QThreadPool()
        print("Multithreading with maximum %d threads" % self.threadpool.maxThreadCount())

    def none(self):
        pass

    def set_serial_file_handle(self, fd):
        self.serial = fd

    @staticmethod
    def run_time():
        t0 = time.time()
        while True:
            yield(time.time() - t0)

    def _set_analysis_function(self, function_name):
        self.addition_analysis = True
        self.analysis_function = function_name

    def unpack_data(self, data):
        word_1 = int(data, 16) & int('FFFF', 16)
        word_2 = int(data, 16) & int('FFFF0000', 16)
        word_3 = int(data, 16) & int('FFFF00000000', 16)
        word_4 = int(data, 16) & int('FFFF000000000000', 16)

        return word_1, word_2, word_3, word_4

    def add_data(self, channel):
        if channel ==  'chan1':
            self.add_data_1 ^= True
        if channel ==  'chan2':
            self.add_data_2 ^= True
        if channel ==  'chan3':
            self.add_data_3 ^= True
        if channel ==  'chan4':
            self.add_data_4 ^= True
        else:
            pass

    def get_chan(self, channel):
        if channel ==  'chan1':
            return self.ydata_chan1
        if channel ==  'chan2':
            return self.ydata_chan2
        if channel ==  'chan3':
            return self.ydata_chan3
        if channel ==  'chan4':
            return self.ydata_chan4
        else:
            return self.ydata_chan1

    def set_chan(self, channel):
        self.current_channel = channel

    def _get_data(self, command):
        try:
            self.serial.send(command='VAL')
            self.serial.serial.flush()

            if self.serial.serial.in_waiting > 0:
                data = self.serial.read()
                data1, data2, data3, data4  = self.unpack_data(data)


                data = self.scale_factor*float(data1)
                self.ydata_chan1.shift(data)

                data = self.scale_factor * float(data2)
                self.ydata_chan2.shift(data)

                data = self.scale_factor * float(data3)
                self.ydata_chan3.shift(data)

                data = self.scale_factor * float(data4)
                self.ydata_chan4.shift(data)

#                self.get_chan(self.current_channel).shift(data)
            else:
                pass

            self.current_time = next(self.time_iter)
            self.tdata.shift(command)

            self.lines.set_data(self.tdata.to_numpy(), self.get_chan(self.current_channel).to_numpy()),
            self.axes_top.set_xlim(self.tdata.to_numpy().min(), self.tdata.to_numpy().max())
            self.axes_bot.set_xlim(self.tdata.to_numpy().min(), self.tdata.to_numpy().max())


            if (self.addition_analysis):
                self.analysis_function_dispatcher[self.analysis_function]()
            if (self.write):
                self.write_data(round(self.current_time, 3), data)

        except serial.SerialException:
            print('Serial Exception: Error reading port.')

    def _analysis_rolling_average(self):
        avg_data, stdev = self.analysis.rolling_average(self.get_chan(self.current_channel).to_numpy()[-11:-1])

        self.avg_data.shift(avg_data)
        self.stdev_data.shift(stdev)

        self.axes_bot.collections.clear()
        self.axes_bot.set_ylim(0, 1050)
        self.axes_bot.fill_between(self.tdata.to_numpy(),
                                   self.avg_data.to_numpy() - self.stdev_data.to_numpy(),
                                   self.avg_data.to_numpy() + self.stdev_data.to_numpy(),
                                   alpha=0.4,
                                   color='xkcd:seafoam')

        self.avg_lines.set_data(self.tdata.to_numpy(), self.avg_data.to_numpy()),

    def _auto_correlation(self):
        auto_correlation_data = self.analysis.auto_correlation(self.get_chan(self.current_channel).to_numpy()[-11:-1])

        self.avg_data.shift(auto_correlation_data)
        self.axes_bot.set_ylim(-1, 1)
        self.avg_lines.set_data(self.tdata.to_numpy(), self.avg_data.to_numpy()),

    def _refresh(self, timer):
        worker = WorkerThreading.Worker(self._get_data, command=timer)
        self.threadpool.start(worker, priority=4)

        return self._get_lines()

    def _get_lines(self):
        return self.lines

    def set_scale_factor(self, scale_factor):
        self.scale_factor = float(scale_factor)
        print(self.scale_factor)

    def plot(self):
        try:
            self.ani = animation.FuncAnimation(self.fig,
                                               self._refresh,
                                               interval=500,
                                               blit=False,
                                               repeat=False)
            self.ani.running = True
            self.draw()
        except Exception as ex:
            print(ex)

    def _write_data(self):
        self.write ^= True

    def write_data(self, tdata, ydata):
        try:
            with open('output.tsv', 'ba') as f:
                f.write("{0}\t{1}\n".format(tdata, ydata).encode())

        except Exception as ex:
            print(ex)

    def on_pause_button_clicked(self):
        if self.ani.running:
            self.ani.event_source.stop()
        else:
            self.ani.event_source.start()
        self.ani.running ^= True

    def on_start_button_clicked(self):
        if self.is_plotting is False:
            self.plot()
            self.is_plotting = True
            self.ani.event_source.start()
        else:
            pass

    def on_close_button_clicked(self):
        try:
            if (self.ani.running):
                self.ani.event_source.stop()
            else:
                pass
        except Exception as ex:
            print('Exception on close: {}'.format(ex))

class PyMonitorMainWindow(object):
    def __init__(self, MainWindow, *args, **kwargs):
        self.serial = None
        self.setup_ui(MainWindow)
#        MainWindow.setFixedSize(1000, 775)

    def setup_ui(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1146, 1031)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        self.plotLayoutWidget = QtWidgets.QWidget(self.centralwidget)
        self.plotLayoutWidget.setGeometry(QtCore.QRect(10, 0, 1101, 571))

        self.plotWidget = QtWidgets.QVBoxLayout(self.plotLayoutWidget)
        self.plotWidget.setContentsMargins(1, 1, 1, 1)
        self.plotWidget.setObjectName("plot_widget")
        spacerItem = QtWidgets.QSpacerItem(20, 245, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)

        self.plot_canvas = PlotCanvas(self, parent=None, width=6, height=5)
        toolbar = NavigationToolbar2QT(self.plot_canvas, self.centralwidget)

        self.plotWidget.addWidget(toolbar)
        self.plotWidget.addWidget(self.plot_canvas)
        self.plotWidget.addItem(spacerItem)

        self.horizontalLayoutWidget = QtWidgets.QWidget(self.centralwidget)
        self.horizontalLayoutWidget.setGeometry(QtCore.QRect(10, 590, 671, 51))
        self.horizontalLayoutWidget.setObjectName("horizontalLayoutWidget")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.horizontalLayoutWidget)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setObjectName("horizontalLayout")

        self.comboBox = QtWidgets.QComboBox(self.horizontalLayoutWidget)
        self.comboBox.setObjectName("comboBox")
        self.horizontalLayout.addWidget(self.comboBox)
        self.comboBox.addItems([comport.device for comport in serial.tools.list_ports.comports()])

        self.pushButton = QtWidgets.QPushButton(self.horizontalLayoutWidget)
        self.pushButton.setObjectName("pushButton")
        self.horizontalLayout.addWidget(self.pushButton)

        self.pushButton_2 = QtWidgets.QPushButton(self.horizontalLayoutWidget)
        self.pushButton_2.setObjectName("pushButton_2")
        self.horizontalLayout.addWidget(self.pushButton_2)

        self.pushButton_3 = QtWidgets.QPushButton(self.horizontalLayoutWidget)
        self.pushButton_3.setObjectName("pushButton_3")
        self.horizontalLayout.addWidget(self.pushButton_3)

        self.pushButton_4 = QtWidgets.QPushButton(self.horizontalLayoutWidget)
        self.pushButton_4.setObjectName("pushButton_4")
        self.horizontalLayout.addWidget(self.pushButton_4)

        self.pushButton_5 = QtWidgets.QPushButton(self.horizontalLayoutWidget)
        self.pushButton_5.setObjectName("pushButton_5")
        self.horizontalLayout.addWidget(self.pushButton_5)

        self.pushButton_6 = QtWidgets.QPushButton(self.horizontalLayoutWidget)
        self.pushButton_6.setObjectName("pushButton_6")
        self.horizontalLayout.addWidget(self.pushButton_6)

        # Define text box
        self.textBox = QtWidgets.QTextEdit(self.centralwidget)
#        self.textBox.setGeometry(QtCore.QRect(10, 670, 1101, 351))
        self.textBox.setGeometry(QtCore.QRect(10, 670, 1101, 251))
        self.textBox.setObjectName("textBox")

        # Define cursor in text box
        self.cursor = QTextCursor(self.textBox.document())

        self.gridLayoutWidget = QtWidgets.QWidget(self.centralwidget)
        self.gridLayoutWidget.setGeometry(QtCore.QRect(710, 580, 401, 80))
        self.gridLayoutWidget.setObjectName("gridLayoutWidget")
        self.gridLayout = QtWidgets.QGridLayout(self.gridLayoutWidget)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.gridLayout.setObjectName("gridLayout")

        self.lineEdit = QtWidgets.QLineEdit(self.gridLayoutWidget)
        self.lineEdit.setEnabled(True)
        self.lineEdit.setObjectName("lineEdit")
        self.gridLayout.addWidget(self.lineEdit, 0, 1, 1, 1)

        self.label = QtWidgets.QLabel(self.gridLayoutWidget)
        self.label.setObjectName("label")
        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)

        self.lineEdit_2 = QtWidgets.QLineEdit(self.gridLayoutWidget)
        self.lineEdit_2.setObjectName("lineEdit_2")
        self.gridLayout.addWidget(self.lineEdit_2, 1, 1, 1, 1)

        self.label_2 = QtWidgets.QLabel(self.gridLayoutWidget)
        self.label_2.setObjectName("label_2")
        self.gridLayout.addWidget(self.label_2, 1, 0, 1, 1)

        self.pushButton_7 = QtWidgets.QPushButton(self.gridLayoutWidget)
        self.pushButton_7.setObjectName("pushButton_7")
        self.gridLayout.addWidget(self.pushButton_7, 0, 2, 1, 1)

        self.pushButton_8 = QtWidgets.QPushButton(self.gridLayoutWidget)
        self.pushButton_8.setObjectName("pushButton_8")
        self.gridLayout.addWidget(self.pushButton_8, 1, 2, 1, 1)

        self.pushButton_9 = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_9.setGeometry(QtCore.QRect(80, 950, 101, 41))
        self.pushButton_9.setObjectName("pushButton_9")

        self.pushButton_10 = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_10.setGeometry(QtCore.QRect(190, 950, 101, 41))
        self.pushButton_10.setObjectName("pushButton_10")

        self.pushButton_11 = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_11.setGeometry(QtCore.QRect(300, 950, 101, 41))
        self.pushButton_11.setObjectName("pushButton_11")

        self.pushButton_12 = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_12.setGeometry(QtCore.QRect(410, 950, 101, 41))
        self.pushButton_12.setObjectName("pushButton_12")

        self.label_image = QtWidgets.QLabel(self.centralwidget)
        self.image_profile = QtGui.QImage('graphics\octocat.svg')
        self.image_profile = self.image_profile.scaled(45, 45,
                                                       aspectRatioMode=QtCore.Qt.KeepAspectRatio,
                                                       transformMode=QtCore.Qt.SmoothTransformation)
        self.label_image.setPixmap(QtGui.QPixmap.fromImage(self.image_profile))
        self.label_image.setGeometry(QtCore.QRect(20, 950, 51, 41))

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 1146, 21))
        self.menubar.setObjectName("menubar")
        self.menupymonitor = QtWidgets.QMenu(self.menubar)
        self.menupymonitor.setObjectName("menupymonitor")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.menubar.addAction(self.menupymonitor.menuAction())

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

        # Button Hooks
        self.pushButton.clicked.connect(self.plot_canvas._write_data)
        self.pushButton_2.clicked.connect(lambda: self.plot_canvas.set_chan('chan1'))
        self.pushButton_3.clicked.connect(lambda: self.plot_canvas.set_chan('chan2'))
        self.pushButton_4.clicked.connect(lambda: self.plot_canvas.set_chan('chan3'))
        self.pushButton_5.clicked.connect(lambda: self.plot_canvas.set_chan('chan4'))
        self.pushButton_6.clicked.connect(lambda: self.plot_canvas._set_analysis_function('rolling-average'))
        self.pushButton_8.clicked.connect(lambda: self.plot_canvas.set_scale_factor(self.lineEdit_2.text()))
        self.pushButton_9.clicked.connect(self.connect)
        self.pushButton_10.clicked.connect(self.plot_canvas.on_start_button_clicked)
        self.pushButton_11.clicked.connect(self.plot_canvas.on_pause_button_clicked)
        self.pushButton_12.clicked.connect(self.close)

    def print_box(self, msg):
        '''
        Wrapper function to print to front-end text box.
        :param msg: string-type to send to text box.
        :return: None
        '''

        self.cursor.setPosition(0)
        self.textBox.setTextCursor(self.cursor)
        self.textBox.insertPlainText('[{ts}] {msg}\n'.format(ts=time.ctime(time.time())[11:-5], msg=msg))


    def connect(self):
        '''
        Create instance serial port handler, Connect to serial port. Pass returned info to text box.
        :return: None
        '''

        try:
            self.serial = SerialPort(port=self.comboBox.currentText())
            self.plot_canvas.set_serial_file_handle(self.serial)
            self.print_box('Connected to serial port: {port}'.format(port=self.serial.port))
        except serial.SerialException as ex:
            self.print_box(
                'Failure to connect to communications port: {port}\n\t error: {error}'.format(port=self.serial.port,
                                                                                              error=ex))

    def close(self):

        try:
            self.threadpool.waitForDone(2000)
            self.plot_canvas.on_close_button_clicked()

            if self.serial._is_open():
                self.serial.disconnect()

        except Exception as ex:
            self.print_box('Error = {}'.format(ex))
        finally:
            self.pushButton_10.clicked.disconnect(self.plot_canvas.on_start_button_clicked)
            self.pushButton_11.clicked.disconnect(self.plot_canvas.on_pause_button_clicked)
            self.pushButton_12.clicked.disconnect(self.close)
            self.plot_canvas.close_event(guiEvent=MainWindow.close())
            MainWindow.close()

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
        self.pushButton.setText(_translate("MainWindow", "Record Data"))
        self.pushButton_2.setText(_translate("MainWindow", "Data 1"))
        self.pushButton_3.setText(_translate("MainWindow", "Data 2"))
        self.pushButton_4.setText(_translate("MainWindow", "Data 3"))
        self.pushButton_5.setText(_translate("MainWindow", "Data 4"))
        self.pushButton_6.setText(_translate("MainWindow", "Rolling Average"))
        self.label.setText(_translate("MainWindow", "Scale X"))
        self.label_2.setText(_translate("MainWindow", "Scale Y"))
        self.pushButton_7.setText(_translate("MainWindow", "Set"))
        self.pushButton_8.setText(_translate("MainWindow", "Set"))
        self.pushButton_9.setText(_translate("MainWindow", "Connect"))
        self.pushButton_10.setText(_translate("MainWindow", "Plot"))
        self.pushButton_11.setText(_translate("MainWindow", "Pause"))
        self.pushButton_12.setText(_translate("MainWindow", "Close"))
        self.menupymonitor.setTitle(_translate("MainWindow", "pymonitor"))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = PyMonitorMainWindow(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())
