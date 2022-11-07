import sys
import argparse
import asyncio
import usb.util
import numpy as np
import libusb_package
import usb.core
import usb.backend.libusb1
from contextlib import contextmanager
import cv2
from datetime import datetime 
from collections import deque
from tqdm import tqdm, trange
from enum import IntEnum
from queue import Queue
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread
from PyQt5.QtWidgets import QTextEdit, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QMainWindow, QMessageBox, QApplication, QLabel
from PyQt5.QtGui import QTextCursor
import threading
from time import sleep
import pyqtgraph as pg
from pyueye import ueye
import numpy as np
import os 
import re 

#many open functions are imported, need just this to write to a file!
open_builtin = open
def load_style_sheet(fname):
    with open_builtin(fname, 'r') as fh:
        return '\n'.join(fh.readlines())
# First, get current stdout to return at the end! Let's be clean, yeah?
O_STDOUT = sys.stdout

class log_levels(IntEnum):
    DEBUG = 0
    INFO = 1
    CRITICAL = 2
    ERROR = 3

#Main window instance, had to move error catching dialog to 
# this little function to make thread safe given the shit show
# that is this script
MAIN_WINDOW = None
def with_error_catcher(f, f_c=None, *args, **kwargs):
    try:
        f(*args, **kwargs)
    except Exception as e:
        QMessageBox.critical(
            MAIN_WINDOW,
            "Error",
            str(e),
        )
        if f_c is not None: f_c()

class customLogger:
    def __init__(self, fname=None):
        if fname is None:
            t = re.match(r'(.+)\.(.+)', str(datetime.now()), re.M | re.I).group(1) #remove microseconds
            now = t.split(' ')
            self.fname = f'starguide_{now[0]}_{now[1]}.log'
        else:
            self.fname = fname
        self.d = {}
        for l in list(log_levels):
            self.d[l.value] = l.name
        self.uninit_msgs = ""
        self.data = "" #list of strings to save

    def log(self, s, level=0, init=False):
        t = datetime.now()
        msg = f'{t.date()} {t.time()}   -   {__name__}   -   {self.d[level]}   -   {s}'
        if init: self.uninit_msgs = self.uninit_msgs + '\n' + msg
        print(msg)

    def write_to_file(self):
        C_STDOUT = sys.stdout
        sys.stdout = O_STDOUT
        with open_builtin(self.fname, 'w') as sys.stdout:
            print(self.uninit_msgs + '\n' + self.data)
        sys.stdout = C_STDOUT

@contextmanager
def gui_environment():
    """ 
    Prepare the environment in which GUI will run by setting 
    the PyQtGraph QT library to PyQt5 while GUI is running. Revert back when done.
    """
    old_qt_lib = os.environ.get(
        "PYQTGRAPH_QT_LIB", "PyQt5"
    )  # environment variable might not exist
    os.environ["PYQTGRAPH_QT_LIB"] = "PyQt5"
    yield
    os.environ["PYQTGRAPH_QT_LIB"] = old_qt_lib

@contextmanager
def rowmajor_axisorder():
    """
    Context manager that sets the PyQtGraph image axis order to row-major.
    The environment is reset to the initial value after context close.
    """
    old_image_axis_order = pg.getConfigOption("imageAxisOrder")
    pg.setConfigOptions(imageAxisOrder="row-major")
    yield
    pg.setConfigOptions(imageAxisOrder=old_image_axis_order)

class StarGuideError(Exception):
    pass

class Editor(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.textChanged.connect(self.autoResize)

    def autoResize(self):
        self.document().setTextWidth(self.viewport().width())
        margins = self.contentsMargins()
        height = int(self.document().size().height() + margins.top() + margins.bottom())
        self.setFixedHeight(min(height, 100))

    def resizeEvent(self, event):
        self.autoResize()

# The new Stream Object which replaces the default stream associated with sys.stdout
# This object just puts data in a queue!

class WriteStream(object):
    def __init__(self,queue):
        self.queue = queue

    def write(self, text):
        self.queue.put(text)

    def flush(self):
        return

# A QObject (to be run in a QThread) which sits waiting for data to come through a Queue.Queue().
# It blocks until data is available, and one it has got something from the queue, it sends
# it to the "MainThread" by emitting a Qt Signal 
class Receiver(QObject):
    mysignal = pyqtSignal(str)

    def __init__(self,queue,*args,**kwargs):
        QObject.__init__(self,*args,**kwargs)
        self.queue = queue

    @pyqtSlot()
    def run(self):
        while True:
            text = self.queue.get()
            self.mysignal.emit(text)


def _make_do(cmd, doc=None):
    def f(self, xx=None, *nn):
        self.do(cmd, xx, *nn)
    if doc is not None:
        f.__doc__ = doc
    return f


def _make_ask(cmd, doc=None, conv=int):
    assert cmd.endswith("?")
    def f(self, xx=None, *nn):
        ret = self.ask(cmd, xx, *nn)
        ret = conv(ret)
        return ret
    if doc is not None:
        f.__doc__ = doc
    return f


class NewFocus8742Protocol:
    """New Focus/Newport 8742 Driver.

    Four Channel Picomotor Controller and Driver Module, Open-Loop, 4 Channel.
    https://www.newport.com/p/8742
    """
    poll_interval = .01

    def fmt_cmd(self, cmd, xx=None, *nn):
        """Format a command.

        Args:
            cmd (str): few-letter command
            xx (int, optional for some commands): Motor channel
            nn (multiple int, optional): additional parameters
        """
        if xx is not None:
            cmd = "{:d}".format(xx) + cmd
        if nn:
            cmd += ", ".join("{:d}".format(n) for n in nn)
        return cmd

    def do(self, cmd, xx=None, *nn):
        """Format and send a command to the device

        See Also:
            :meth:`fmt_cmd`: for the formatting and additional
                parameters.
        """
        cmd = self.fmt_cmd(cmd, xx, *nn)
        assert len(cmd) < 64
        # logger.debug("do %s", cmd)
        self._writeline(cmd)

    def ask(self, cmd, xx=None, *nn):
        """Execute a command and return a response.

        The command needs to include the final question mark.

        See Also:
            :meth:`fmt_cmd`: for the formatting and additional
                parameters.
        """
        assert cmd.endswith("?")
        self.do(cmd, xx, *nn)
        ret = self._readline()
        # logger.debug("ret %s", ret)
        return ret

    def _writeline(self, cmd):
        return

    def _readline(self):
        return

    identify = _make_ask("*IDN?",
            """Get product identification string.

            This query will cause the instrument to return a unique
            identification string. This similar to the Version (VE) command but
            provides more information. In response to this command the
            controller replies with company name, product model name, firmware
            version number, firmware build date, and controller serial number.
            No two controllers share the same model name and serial numbers,
            therefore this information can be used to uniquely identify a
            specific controller.""", conv=str)

    recall = _make_do("*RCL",
            """Recall settings.

            This command restores the controller working parameters from values
            saved in its nonvolatile memory. It is useful when, for example,
            the user has been exploring and changing parameters (e.g.,
            velocity) but then chooses to reload from previously stored,
            qualified settings. Note that “\*RCL 0” command just restores the
            working parameters to factory default settings. It does not change
            the settings saved in EEPROM.""")

    reset = _make_do("*RST",
            """Reset.

            This command performs a “soft” reset or reboot of the controller
            CPU. Upon restart the controller reloads parameters (e.g., velocity
            and acceleration) last saved in non-volatile memory. Note that upon
            executing this command, USB and Ethernet communication will be
            interrupted for a few seconds while the controller re-initializes.
            Ethernet communication may be significantly delayed (~30 seconds)
            in reconnecting depending on connection mode (Peer-to-peer, static
            or dynamic IP mode) as the PC and controller are negotiating TCP/IP
            communication.""")

    abort = _make_do("AB",
            """Abort motion.

            This command is used to instantaneously stop any motion that is in
            progress. Motion is stopped abruptly. For stop with deceleration
            see ST command which uses programmable acceleration/deceleration
            setting.""")

    set_acceleration = _make_do("AC",
            """Set acceleration.

            This command is used to set the acceleration value for an axis. The
            acceleration setting specified will not have any effect on a move
            that is already in progress. If this command is issued when an
            axis' motion is in progress, the controller will accept the new
            value but it will use it for subsequent moves only. """)

    get_acceleration = _make_ask("AC?",
            """Get acceleration.

            This command is used to query the acceleration value for an axis.""")

    set_home = _make_do("DH",
            """Set home position.

            This command is used to define the “home” position for an axis. The
            home position is set to 0 if this command is issued without “nn”
            value. Upon receipt of this command, the controller will set the
            present position to the specified home position. The move to
            absolute position command (PA) uses the “home” position as
            reference point for moves.""")

    get_home = _make_ask("DH?",
            """Get home position.

            This command is used to query the home position value for an
            axis.""")

    check_motor = _make_do("MC",
            """Motor check.

            This command scans for motors connected to the controller, and sets
            the motor type based on its findings. If the piezo motor is found
            to be type 'Tiny' then velocity (VA) setting is automatically
            reduced to 1750 if previously set above 1750. To accomplish this
            task, the controller commands each axis to make a one-step move in
            the negative direction followed by a similar step in the positive
            direction. This process is repeated for all the four axes starting
            with the first one. If this command is issued when an axis is
            moving, the controller will generate “MOTION IN PROGRESS” error
            message.""")

    done = _make_ask("MD?",
            """Motion done query.

            This command is used to query the motion status for an axis.""")

    move = _make_do("MV",
            """Indefinite move.

            This command is used to move an axis indefinitely. If this command
            is issued when an axis' motion is in progress, the controller will
            ignore this command and generate “MOTION IN PROGRESS” error
            message. Issue a Stop (ST) or Abort (AB) motion command to
            terminate motion initiated by MV""")

    set_position = _make_do("PA",
            """Target position move command.

            This command is used to move an axis to a desired target (absolute)
            position relative to the home position defined by DH command. Note
            that DH is automatically set to 0 after system reset or a power
            cycle. If this command is issued when an axis' motion is in
            progress, the controller will ignore this command and generate
            “MOTION IN PROGRESS” error message. The direction of motion and
            number of steps needed to complete the motion will depend on where
            the motor count is presently at before the command is issued. Issue
            a Stop (ST) or Abort (AB) motion command to terminate motion
            initiated by PA""")

    get_position = _make_ask("PA?",
            """Get target position.

            This command is used to query the target position of an axis.""")

    set_relative = _make_do("PR",
            """Relative move.

            This command is used to move an axis by a desired relative
            distance. If this command is issued when an axis' motion is in
            progress, the controller will ignore this command and generate
            “MOTION IN PROGRESS” error message. Issue a Stop (ST) or Abort (AB)
            motion command to terminate motion initiated by PR""")

    get_relative = _make_ask("PR?",
            """This command is used to query the target position of an
            axis.""")

    set_type = _make_do("QM",
            """Motor type set command.

            This command is used to manually set the motor type of an axis.
            Send the Motors Check (MC) command to have the controller determine
            what motors (if any) are connected. Note that for motor type
            'Tiny', velocity should not exceed 1750 step/sec. To save the
            setting to non-volatile memory, issue the Save (SM) command. Note
            that the controller may change this setting if auto motor detection
            is enabled by setting bit number 0 in the configuration register to
            0 (default) wit ZZ command. When auto motor detection is enabled
            the controller checks motor presence and type automatically during
            all moves and updates QM status accordingly.""")

    get_type = _make_ask("QM?",
            """Get motor type.

            This command is used to query the motor type of an axis. It is
            important to note that the QM? command simply reports the present
            motor type setting in memory. It does not perform a check to
            determine whether the setting is still valid or corresponds with
            the motor connected at that instant. If motors have been removed
            and reconnected to different controller channels or if this is the
            first time, connecting this system then issuing the Motor Check
            (MC) command is recommended. This will ensure an accurate QM?
            command response.""")

    position = _make_ask("TP?",
            """Get actual position.

            This command is used to query the actual position of an axis. The
            actual position represents the internal number of steps made by the
            controller relative to its position when controller was powered ON
            or a system reset occurred or Home (DH) command was received. Note
            that the real or physical position of the actuator/motor may differ
            as a function of mechanical precision and inherent open-loop
            positioning inaccuracies.""")

    set_velocity = _make_do("VA",
            """Set Velocity.

            This command is used to set the velocity value for an axis. The
            velocity setting specified will not have any effect on a move that
            is already in progress. If this command is issued when an axis'
            motion is in progress, the controller will accept the new value but
            it will use it for subsequent moves only. The maximum velocity for
            a 'Standard' Picomotor is 2000 steps/sec, while the same for a
            'Tiny' Picomotor is 1750 steps/sec """)

    get_velocity = _make_ask("VA?",
            """Get Velocity.

            This command is used to query the velocity value for an axis.""")

    stop = _make_do("ST",
            """Stop motion.

            This command is used to stop the motion of an axis. The controller
            uses acceleration specified using AC command to stop motion. If no
            axis number is specified, the controller stops the axis that is
            currently moving. Use Abort (AB) command to abruptly stop motion
            without deceleration.""")

    error_message = _make_ask("TB?",
            """Query error code and the associated message.

            The error code is one numerical value up to three(3) digits long.
            (see Appendix for complete listing) In general, non-axis specific
            errors numbers range from 0- 99. Axis-1 specific errors range from
            100-199, Axis-2 errors range from 200-299 and so on. The message is
            a description of the error associated with it. All arguments are
            separated by commas. Note: Errors are maintained in a FIFO buffer
            ten(10) elements deep. When an error is read using TB or TE, the
            controller returns the last error that occurred and the error
            buffer is cleared by one(1) element. This means that an error can
            be read only once, with either command.""", conv=str)

    error_code = _make_ask("TE?",
            """Get Error code.

            This command is used to read the error code. The error code is one
            numerical value up to three(3) digits long. (see Appendix for
            complete listing) In general, non-axis specific errors numbers
            range from 0-99. Axis-1 specific errors range from 100-199, Axis-2
            errors range from 200-299 and so on. Note: Errors are maintained in
            a FIFO buffer ten(10) elements deep. When an error is read using TB
            or TE, the controller returns the last error that occurred and the
            error buffer is cleared by one(1) element. This means that an error
            can be read only once, with either command.""")

    def finish(self, xx=None):
        while not self.done(xx):
            asyncio.sleep(self.poll_interval)

    def ping(self):
        try:
            self.ask("VE?")
        except asyncio.CancelledError:
            raise
        except:
            logger.warning("ping failed", exc_info=True)
            return False
        return True

class NewFocus8742USB(NewFocus8742Protocol):
    eol_write = b"\r"
    eol_read = b"\r\n"

    @classmethod
    def create(cls, idVendor=0x104d, idProduct=0x4000):
        self = NewFocus8742USB()
        self.idProduct = int(idProduct, 16)
        self.idVendor = int(idVendor, 16)
        self.connect()
        self.flush()
        return self

    def connect(self,**kwargs):
        """Connect to a Newfocus/Newport 8742 controller over USB.
        Args:
            **kwargs: passed to `usb.core.find`
        Returns:
            NewFocus8742: Driver instance.
        """

        # find the device
        self.dev = usb.core.find(
                        idProduct=self.idProduct,
                        idVendor=self.idVendor, **kwargs
                        )
       
        if self.dev is None:
            raise ValueError('Device not found')
        else:
            # logging.info('Connected!')
            pass
        # set the active configuration. With no arguments, the first
        # configuration will be the active one
        self.dev.set_configuration()

        # get an endpoint instance
        cfg = self.dev.get_active_configuration()
        intf = cfg[(0,0)]

        self.ep_out = usb.util.find_descriptor(
            intf,
            # match the first OUT endpoint
            custom_match = \
            lambda e: \
                usb.util.endpoint_direction(e.bEndpointAddress) == \
                usb.util.ENDPOINT_OUT)

        self.ep_in = usb.util.find_descriptor(
            intf,
            # match the first IN endpoint
            custom_match = \
            lambda e: \
                usb.util.endpoint_direction(e.bEndpointAddress) == \
                usb.util.ENDPOINT_IN)

        assert (self.ep_out and self.ep_in) is not None
        # Confirm connection to user
        resp = self.ask('VE?')
        # print(resp)
        # print("Connected to Motor Controller Model {}. Firmware {} {} {}\n".format(*resp.split(' ')))
        for m in range(1, 5):
            resp = self.ask("{}QM?".format(m))
            # print("Motor #{motor_number}: {status}".format(
            #     motor_number=m,
            #     status=MOTOR_TYPE[resp[-1]]
            # ))

    def flush(self):
        """Drain the input buffer from read data."""
        while True:
            try:
                self.ep_in.read(64, timeout=10)
            except usb.core.USBError:
                break

    def close(self):
        usb.util.dispose_resources(self.dev)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _writeline(self, cmd):
        self.ep_out.write(cmd.encode() + self.eol_write)
        # logger.debug(f"Successfully wrote {cmd.encode()}", exc_info=True)

    def _readline(self):
        # This is obviously not asynchronous
        r = self.ep_in.read(64).tobytes()
        assert r.endswith(self.eol_read)
        r = r[:-2].decode()
        # logger.debug(f"Successfully read {r}", exc_info=True)
        return r

class NewFocus8742TCP(NewFocus8742Protocol):
    eol_write = b"\r"
    eol_read = b"\r\n"

    @classmethod
    def create(cls, host, port=23, **kwargs):
        self = NewFocus8742TCP()
        self.host = host
        self.port = port
        self.connect(**kwargs)
        return self

    def connect(self, **kwargs):
        """Connect to a Newfocus/Newport 8742 controller over Ethernet/TCP.
        Args:
            host (str): Hostname or IP address of the target device.
        Returns:
            NewFocus8742: Driver instance.
        """
        reader, writer = asyncio.open_connection(self.host, self.port, **kwargs)
        self._reader = reader
        self._writer = writer
        # undocumented? garbage?
        v = reader.read(6)
        logger.debug("identifier/serial (?): %s", v)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        self._writer.close()

    def _writeline(self, cmd):
        self._writer.write(cmd.encode() + self.eol_write)

    def _readline(self):
        r = self._reader.readline()
        assert r.endswith(self.eol_read)
        return r[:-2].decode()

# ____________________________________________________________________________________________________________________________

#Libraries
from pyueye import ueye
import numpy as np

class uEyeCamera:
    def __init__(self, HID=0):
        #---------------------------------------------------------------------------------------------------------------------------------------

        #Variables
        self.hCam = ueye.HIDS(HID)             #0: first available camera;  1-254: The camera with the specified camera ID
        self.sInfo = ueye.SENSORINFO()
        self.cInfo = ueye.CAMINFO()
        self.pcImageMemory = ueye.c_mem_p()
        self.MemID = ueye.int()
        self.rectAOI = ueye.IS_RECT()
        self.pitch = ueye.INT()
        self.nBitsPerPixel = ueye.INT(24)    #24: bits per pixel for color mode; take 8 bits per pixel for monochrome
        self.channels = 3                        #3: channels for color mode(RGB); take 1 channel for monochrome
        self.m_nColorMode = ueye.INT()       # Y8/RGB16/RGB24/REG32
        self.bytes_per_pixel = int(self.nBitsPerPixel / 8)
        self.pixelclock = ueye.UINT()
        #---------------------------------------------------------------------------------------------------------------------------------------
        # print("START")
        # print()


        # Starts the driver and establishes the connection to the camera
        self.nRet = ueye.is_InitCamera(self.hCam, None)
        if self.nRet != ueye.IS_SUCCESS:
            print("is_InitCamera ERROR")

        # Reads out the data hard-coded in the non-volatile camera memory and writes it to the data structure that cInfo points to
        self.nRet = ueye.is_GetCameraInfo(self.hCam, self.cInfo)
        if self.nRet != ueye.IS_SUCCESS:
            print("is_GetCameraInfo ERROR")

        # You can query additional information about the sensor type used in the camera
        self.nRet = ueye.is_GetSensorInfo(self.hCam, self.sInfo)
        if self.nRet != ueye.IS_SUCCESS:
            print("is_GetSensorInfo ERROR")

        self.nRet = ueye.is_ResetToDefault( self.hCam)
        if self.nRet != ueye.IS_SUCCESS:
            print("is_ResetToDefault ERROR")

        # Set display mode to DIB
        self.nRet = ueye.is_SetDisplayMode(self.hCam, ueye.IS_SET_DM_DIB)

        # Set the right color mode
        if int.from_bytes(self.sInfo.nColorMode.value, byteorder='big') == ueye.IS_COLORMODE_BAYER:
            # setup the color depth to the current windows setting
            ueye.is_GetColorDepth(self.hCam, self.nBitsPerPixel, self.m_nColorMode)
            self.bytes_per_pixel = int(self.nBitsPerPixel / 8)
            # print("IS_COLORMODE_BAYER: ", )
            # print("\tm_nColorMode: \t\t", self.m_nColorMode)
            # print("\tnBitsPerPixel: \t\t", self.nBitsPerPixel)
            # print("\tbytes_per_pixel: \t\t", self.bytes_per_pixel)
            # print()

        elif int.from_bytes(self.sInfo.nColorMode.value, byteorder='big') == ueye.IS_COLORMODE_CBYCRY:
            # for color camera models use RGB32 mode
            self.m_nColorMode = ueye.IS_CM_BGRA8_PACKED
            self.nBitsPerPixel = ueye.INT(32)
            self.bytes_per_pixel = int(self.nBitsPerPixel / 8)
            # print("IS_COLORMODE_CBYCRY: ", )
            # print("\tm_nColorMode: \t\t", self.m_nColorMode)
            # print("\tnBitsPerPixel: \t\t", self.nBitsPerPixel)
            # print("\tbytes_per_pixel: \t\t", self.bytes_per_pixel)
            # print()

        elif int.from_bytes(self.sInfo.nColorMode.value, byteorder='big') == ueye.IS_COLORMODE_MONOCHROME:
            # for color camera models use RGB32 mode
            self.m_nColorMode = ueye.IS_CM_MONO8
            self.nBitsPerPixel = ueye.INT(8)
            self.bytes_per_pixel = int(self.nBitsPerPixel / 8)
            # print("IS_COLORMODE_MONOCHROME: ", )
            # print("\tm_nColorMode: \t\t", self.m_nColorMode)
            # print("\tnBitsPerPixel: \t\t", self.nBitsPerPixel)
            # print("\tbytes_per_pixel: \t\t", self.bytes_per_pixel)
            # print()

        else:
            # for monochrome camera models use Y8 mode
            self.m_nColorMode = ueye.IS_CM_MONO8
            self.nBitsPerPixel = ueye.INT(8)
            self.bytes_per_pixel = int(self.nBitsPerPixel / 8)
            # print("else")

        # Can be used to set the size and position of an "area of interest"(AOI) within an image
        self.nRet = ueye.is_AOI(self.hCam, ueye.IS_AOI_IMAGE_GET_AOI, self.rectAOI, ueye.sizeof(self.rectAOI))
        # if self.nRet != ueye.IS_SUCCESS:
            # print("is_AOI ERROR")

        self.width = self.rectAOI.s32Width
        self.height = self.rectAOI.s32Height

        # Set PixelClock
        if ueye.is_PixelClock(self.hCam, ueye.IS_PIXELCLOCK_CMD_SET, ueye.UINT(12), ueye.sizeof(self.pixelclock)):
            print('error while setting pixelclock')
        ueye.is_PixelClock(self.hCam, ueye.IS_PIXELCLOCK_CMD_GET, self.pixelclock, ueye.sizeof(self.pixelclock))

        # Prints out some information about the camera and the sensor
        # print("Camera model:\t\t", self.sInfo.strSensorName.decode('utf-8'))
        # print("Camera serial no.:\t", self.cInfo.SerNo.decode('utf-8'))
        # print("Maximum image width:\t", self.width)
        # print("Maximum image height:\t", self.height)

        self.allocate_image_memory()     
        self.centroids = deque(maxlen=1000)
        self.centroids.append([np.NaN, np.NaN])
        self.centroids.append([np.NaN, np.NaN])

    def allocate_image_memory(self):
        #---------------------------------------------------------------------------------------------------------------------------------------

        # Allocates an image memory for an image having its dimensions defined by width and height and its color depth defined by nBitsPerPixel
        self.nRet = ueye.is_AllocImageMem(self.hCam, self.width, self.height, self.nBitsPerPixel, self.pcImageMemory, self.MemID)
        if self.nRet != ueye.IS_SUCCESS:
            print("is_AllocImageMem ERROR")
        else:
            # Makes the specified image memory the active memory
            self.nRet = ueye.is_SetImageMem(self.hCam, self.pcImageMemory, self.MemID)
            if self.nRet != ueye.IS_SUCCESS:
                print("is_SetImageMem ERROR")
            else:
                # Set the desired color mode
                self.nRet = ueye.is_SetColorMode(self.hCam, self.m_nColorMode)



        # Activates the camera's live video mode (free run mode)
        self.nRet = ueye.is_CaptureVideo(self.hCam, ueye.IS_DONT_WAIT)
        if self.nRet != ueye.IS_SUCCESS:
            print("is_CaptureVideo ERROR")

        # Enables the queue mode for existing image memory sequences
        self.nRet = ueye.is_InquireImageMem(self.hCam, self.pcImageMemory, self.MemID, self.width, self.height, self.nBitsPerPixel, self.pitch)
        if self.nRet != ueye.IS_SUCCESS:
            print("is_InquireImageMem ERROR")
        # else:
            # print("Press q to leave the programm")

    def get_image(self):
        array = ueye.get_data(self.pcImageMemory, self.width, self.height, self.nBitsPerPixel, self.pitch, copy=False)
        self.bytes_per_pixel = int(self.nBitsPerPixel / 8)
        # ...reshape it in an numpy array...
        self.frame = np.reshape(array,(self.height.value, self.width.value, self.bytes_per_pixel))
        return self.frame

    def get_centroid(self):
        self.get_image()
        try:
            MAX = max(np.percentile(self.frame, 99), 127)
            ret,thresh = cv2.threshold(self.frame,MAX,255,0)
            M = cv2.moments(thresh)
            try:
                self.centroid = np.array([ float(M['m01']/M['m00']), float(M['m10']/M['m00'])])
            except ZeroDivisionError:
                self.centroid = np.array([np.nan, np.nan])
            # self.frame = self.get_image()
            # m,n, _ = self.frame.shape
            # self.centroid = np.unravel_index(np.argmax(self.frame), (m,n))
            # print(centroid, self.centroid)
        except (RuntimeWarning, ValueError) as e:
            self.centroid = np.array([np.nan, np.nan])
            pass
        self.centroids.append(self.centroid)
        return self.centroid

    def get_mean_centroid(self, num_c):
        centroids = np.array(self.centroids)
        if len(centroids) < num_c:
            return np.nanmean(centroids, axis=0)[::-1]
        else:
            return np.nanmean(centroids[:num_c:-1, :], axis=0)[::-1]

    def __del__(self):
        name = self.sInfo.strSensorName.decode('utf-8')
        # Releases an image memory that was allocated using is_AllocImageMem() and removes it from the driver management
        ueye.is_FreeImageMem(self.hCam, self.pcImageMemory, self.MemID)

        # Disables the hCam camera handle and releases the data structures and memory areas taken up by the uEye camera
        ueye.is_ExitCamera(self.hCam)
        # print(f'Camera {name} closed')

# ____________________________________________________________________________________________________________________________
class uEyeMainWindow(QMainWindow):
    def __init__(self, parent, cam1, cam2, target1=None, target2=None, logging=True, **kwargs):
        global MAIN_WINDOW
        super().__init__()
        self.setWindowTitle('StarGuide III')
        self.parent = parent
        self.image_viewer = uEyeViewer(self, cam1, cam2, target1, target2, logging, **kwargs)
        layout = QVBoxLayout()
        layout.addWidget(self.image_viewer)
        self.setCentralWidget(self.image_viewer)
        self.setGeometry(0, 0, 1800, 1000)
        MAIN_WINDOW = self
        self.show()


class uEyeViewer(QWidget):
    """
    Widget containing a main viewer, plus some cursor information.

    Parameters
    ----------
    image : ndarray
    """

    def __init__(self, parent, cam1, cam2, target1=None, target2=None, logging=True, **kwargs):
        super().__init__(parent, **kwargs)
        self.parent = parent
        self.viewer = pg.ImageView()
        self.logging = logging
        # self.viewer.ui.histogram.hide()
        self.cam1 = cam1
        self.cam2 = cam2
        self.target1 = target1
        self.target2 = target2
        self.current_hists = []
        self.current_plot_lines = []
        self.acc = 1
        self.times = deque(maxlen=100)
        self.centroids = deque(maxlen=100)
        self.cursor_info = QLabel("")
        self.cursor_info.setAlignment(pg.QtCore.Qt.AlignCenter)

        self.engage_closed_loop_btn = QPushButton('Engage lock')
        self.engage_closed_loop_btn.setEnabled(True)
        self.engage_closed_loop_btn.clicked.connect(self.engage_closed_loop)

        self.acquire_motion_matrix_btn = QPushButton('Acquire Motion Matrix')
        self.acquire_motion_matrix_btn.setEnabled(True)
        self.acquire_motion_matrix_btn.clicked.connect(self.acquire_matrix)

        self.__cursor_proxy = pg.SignalProxy(
            self.viewer.scene.sigMouseMoved,
            rateLimit=60,
            slot=self.update_cursor_info,
        )

        #do things to redirect stdout
        self.queue = Queue()
        sys.stdout = WriteStream(self.queue)
        # Create thread that will listen on the other end of the queue, and send the text to the textedit in our application
        self.stdout_thread = QThread()
        self.receiver = Receiver(self.queue)
        self.receiver.mysignal.connect(self.append_text)
        self.receiver.moveToThread(self.stdout_thread)
        self.stdout_thread.started.connect(self.receiver.run)
        self.stdout_thread.start()
        self.stdout_box = Editor() #custom QTextEdit class with autoadjust height

        layout = QVBoxLayout(self)
        layout.addWidget(self.viewer)
        layout.addWidget(self.cursor_info)

        btns = QHBoxLayout()
        btns.addWidget(self.acquire_motion_matrix_btn)
        btns.addWidget(self.engage_closed_loop_btn)

        layout.addLayout(btns)
        layout.addWidget(self.stdout_box)

        self.setLayout(layout)

        self.timer = pg.QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(int(1e2))  # fires every 100ms (frame rate 10 Hz, max 14 Hz)


    def update_cursor_info(self, event):
        """Determine cursor information from mouse event."""
        mouse_point = self.viewer.getView().mapSceneToView(event[0])
        i, j = int(mouse_point.y()), int(mouse_point.x())
        try:
            val = self.viewer.getImageItem().image[i, j][0]
        except IndexError:
            val = 0
        self.cursor_info.setText(
            f"Position: ({i},{j}) | Pixel value: {val:.2f} cnts"
        )
    
    def __del__(self):
        self.stdout_thread.terminate()

    def append_text(self,text):
        self.stdout_box.moveCursor(QTextCursor.End)
        self.stdout_box.insertPlainText( text )

    def acquire_matrix(self):
        dialog = QMessageBox.question(
            self,
            "Matrix Acquisition",
            "This action will engage the motors, and move the beam.\nThis machine has no brain; use your own!",
            QMessageBox.Ok,
            QMessageBox.Cancel
        )
        if dialog == QMessageBox.Ok:
            self.acquire_motion_matrix_btn.setText('Acquiring ...')
            with_error_catcher(self.parent.parent.acquire_motion_matrix)
            self.acquire_motion_matrix_btn.setText('Acquire Motion Matrix')

    def change_lock_text(self):
        self.engage_closed_loop_btn.setText('Disengage' if self.parent.parent._alignment_running else 'Engage')


    def engage_closed_loop(self):
        self.change_lock_text()
        self.parent.parent._alignment_running = not self.parent.parent._alignment_running               
        if self.parent.parent._alignment_running:
            dialog = QMessageBox.question(
                self,
                "Engaging Closed Loop",
                "This action will engage the motors, and move the beam.\nThis machine has no brain; use your own!",
                QMessageBox.Ok,
                QMessageBox.Cancel
            )
            if dialog == QMessageBox.Ok:
                self.parent.parent.run()
        else:
            self.parent.parent.stop()

    def update(self):
        self.image1 = self.cam1.get_image().astype(float)
        self.image1 /= self.image1.max()
        self.image2 = self.cam2.get_image().astype(float)
        self.image2 /= self.image2.max()
        self.frame = np.concatenate((self.image1, self.image2), axis=1)
        self.viewer.setImage(self.frame, autoLevels=False, autoRange=False, autoHistogramRange=False)
        # self.viewer.setLevels(min=0, max=np.percentile(self.frame, 99))

        self.centroid_viewer = self.viewer.getView()
        for line in self.current_plot_lines: 
            self.centroid_viewer.removeItem(line)
        self.current_plot_lines = []
        centroids = []
        for idc, (cam, btn, target) in enumerate(zip([self.cam1, self.cam2], [self.viewer.ui.roiBtn, self.viewer.ui.menuBtn], [self.target1, self.target2])):
            y, x = cam.get_centroid()
            centroids.append([y,x])
            btn.setText(f'({x:3.1f},{y:3.1f})')
            # if idc == 0: self.setWindowTitle(f"{x:3.0f}, {y:3.0f}")
            origin = self.cam1.width.value if idc == 1 else 0

            self.current_x_centroid = pg.PlotCurveItem(
                x = origin + x*np.ones((100,)), y = np.linspace(0, cam.height.value, 100), pen=pg.mkPen('g')
            )
            self.current_y_centroid = pg.PlotCurveItem(
                x = origin + np.linspace(0, cam.width.value, 100), y = y*np.ones((100,)), pen=pg.mkPen('g')
            )

            if target is not None:
                x_line = pg.PlotCurveItem(
                    x = origin + target[0]*np.ones((100,)), y = np.linspace(0, cam.height.value, 100), pen=pg.mkPen('r')
                )
                y_line = pg.PlotCurveItem(
                    x = origin + np.linspace(0, cam.width.value, 100), y = target[1]*np.ones((100,)), pen=pg.mkPen('r')
                )
                self.current_plot_lines.append(x_line)
                self.current_plot_lines.append(y_line)         

            self.current_plot_lines.append(self.current_x_centroid)
            self.current_plot_lines.append(self.current_y_centroid)

        if self.logging:
            self.centroids.append(centroids)
            self.times.append(datetime.now())
            if self.acc % 100 == 0:
                logger.data = "\n".join(self.stdout_box.toPlainText().split('\n'))
                logger.write_to_file()
                if os.path.exists('positions.npz'):
                    previous_data = np.load('positions.npz', allow_pickle=True)
                    p_c = previous_data['centroids'].reshape(-1, 2, 2)
                    c_c =  np.array(self.centroids).reshape(-1,2,2)
                    p_t = previous_data['times'].reshape(-1,)
                    c_t = np.array(self.times).reshape(-1,)
                    # logger.log(f"Previous c shape {p_c.shape}, Current {c_c.shape}")
                    # logger.log(f"Previous time shape {p_t.shape}, Current {c_t.shape}")
                    np.savez('positions.npz', 
                        centroids = np.concatenate((p_c, c_c), axis=0), 
                        times = np.concatenate((p_t,c_t), axis=0)
                    )
                else:
                    np.savez('positions.npz', centroids = self.centroids, times = self.times)
        for line in self.current_plot_lines: 
            self.centroid_viewer.addItem(line)
        self.acc += 1

class MOTOR_TYPES(IntEnum):
    NO_MOTOR = 0
    MOTOR_UKNOWN = 1
    TINY = 2
    STANDARD = 3

class StarGuide:
    M1X = 1
    M1Y = 2
    M2X = 3
    M2Y = 4
    MOTOR_CHANNELS = [M1X, M1Y, M2X, M2Y]
    MOTOR_TYPE = MOTOR_TYPES.TINY
    MOTOR_VELOCITY = 1000  # was 1750
    MOTOR_ACCELERATION = 10_000  # was 100_000
    AMM_STEP = 200

    CAM_CHANNELS = [1, 2]
    C1_TARGET = (610, 547)
    C2_TARGET = (560, 581)
    TARGETS = [C1_TARGET, C2_TARGET]

    GAIN = 0.004
    ALIGNMENT_THRESHOLD = 0.5  # min pixel distance to correct for
    MOVEMENT_THRESHOLD = 2500  # max motor movement
    MIN_MOVEMENT_THRESHOLD = 0.2
    SAMPLES = 10

    MOTION_MATRIX_CONSTRAINT = np.array([
        [1, 0, 1, 0],
        [0, 1, 0, 1],
        [0, 0, 1, 0],
        [0, 0, 0, 1]
    ])

    def __init__(self, motion_matrix=None, debug=False):
        if motion_matrix is not None:
            self.mm = motion_matrix
        else:
            if debug:
                logger.log('no motion matrix found; please acquire it', init=True)
        self.debug = debug

        usb.backend.libusb1.get_backend(find_library=libusb_package.find_library)
        self.mc = NewFocus8742USB.create('0x104d', '0x4000')
        self.cams = [uEyeCamera(self.CAM_CHANNELS[0]), uEyeCamera(self.CAM_CHANNELS[1])]
        self.ui_thread = threading.Thread(target=self.__view_worker)
        self.ui_thread.start()
        self._alignment_running = False
        for m_channel in self.MOTOR_CHANNELS:
            self.mc.set_type(m_channel, self.MOTOR_TYPE)
            self.mc.set_velocity(m_channel, self.MOTOR_VELOCITY)
            self.mc.set_acceleration(m_channel, self.MOTOR_ACCELERATION)

    def __del__(self):
        if hasattr(self, 'ui_thread'):
            self.ui_thread.join()

    def __view_worker(self):
        with rowmajor_axisorder():
            app = QApplication([])
            app.setStyleSheet(load_style_sheet('siwickDark.qss'))
            self.viewer = uEyeMainWindow(self, *self.cams, target1=self.C1_TARGET, target2=self.C2_TARGET)
            app.exec_()

    def __align_worker(self):
        while True:
            if self._alignment_running:
                self.align_beam()
            else:
                break

    def run(self):
        self._alignment_running = True
        self._alignment_thread = threading.Thread(target=with_error_catcher(self.__align_worker, self.stop))
        self._alignment_thread.start()

    def stop(self):
        try:
            self._alignment_running = False
            self._alignment_thread.join()
        except AttributeError:
            self._alignment_running = False
        # self.viewer.close()
        # self.ui_thread.join()

    def acquire_motion_matrix(self, n_samples=1):
        mm = np.zeros((n_samples, 4, 4))
        for idn in trange(n_samples, desc='motion matricies'):
            mm_n = np.zeros((4,4))
            for i, m_channel in tqdm(enumerate(self.MOTOR_CHANNELS), total=len(self.MOTOR_CHANNELS), desc='motors', leave=False):
                self.__move_rel(m_channel, -self.AMM_STEP)
                old_cam_poss = []
                for k, cam in enumerate(self.cams):
                    sleep(self.SAMPLES / 9)
                    cam_pos_x, cam_pos_y = cam.get_mean_centroid(self.SAMPLES)
                    old_cam_poss.append((cam_pos_x, cam_pos_y))
                    if self.debug:
                        logger.log(f'for cam {k} found old pos: {cam_pos_x}, {cam_pos_y}')
                self.__move_rel(m_channel, 2*self.AMM_STEP)
                new_cam_poss = []
                for k, cam in enumerate(self.cams):
                    sleep(self.SAMPLES / 9)
                    cam_pos_x, cam_pos_y = cam.get_mean_centroid(self.SAMPLES)
                    new_cam_poss.append((cam_pos_x, cam_pos_y))
                    if self.debug:
                        logger.log(f'for cam {k} found new pos: {cam_pos_x}, {cam_pos_y}')
                for j, (new_pos, old_pos) in enumerate(zip(new_cam_poss, old_cam_poss)):
                    mm_n[2*j, i] = (new_pos[0]-old_pos[0])/self.AMM_STEP
                    mm_n[(2*j)+1, i] = (new_pos[1]-old_pos[1])/self.AMM_STEP
                    if self.debug:
                        logger.log(f'motion_matrix[{2*j},{i}]={mm_n[2*j, i]:+.3f}, motion_matrix[{2*j+1},{i}]={mm_n[(2*j)+1, i]:+.3f}')
                    sleep(2)
                self.__move_rel(m_channel, -self.AMM_STEP)
            mm[idn] = mm_n * self.MOTION_MATRIX_CONSTRAINT
            if self.debug:
                logger.log(f'motion matrix for step {idn+1}/{n_samples}:\n{np.linalg.inv(mm[idn])}')
        logger.log(f'final uninverted motion matrix has sum: {mm.sum()}\n{mm}')
        self.mm = np.linalg.inv(np.average(mm, axis=0))
        logger.log(f'final motion matrix has sum: {self.mm.sum()}\n{self.mm}')

    def __move_rel(self, motor_channel, dist, blocking=True):
        sign = int((int(dist>0))-(int(dist<0)))
        if abs(dist) < self.MIN_MOVEMENT_THRESHOLD:
            dist = 0
        elif abs(dist) < 1:
            dist = 1*sign
        else:
            dist = int(np.rint(dist))
        self.mc.set_relative(motor_channel, dist)
        if self.debug:
            logger.log(f'rel moved motor {motor_channel}: {dist:4.7f}')            
        if blocking:
            while not self.mc.done(motor_channel):
                sleep(0.25)
            sleep(0.25)

    def __move_abs(self, motor_channel, pos, blocking=True):
        self.mc.set_position(motor_channel, pos)
        if self.debug:
            logger.log(f'abs moved motor {motor_channel}: {pos:4.7f}')
        if blocking:
            while not self.mc.done(motor_channel):
                sleep(0.25)
            sleep(0.25)

    def align_beam(self):
        cam_offsets = []
        sleep(self.SAMPLES / 9)
        for cam, target in zip(self.cams, self.TARGETS):
            cam_pos_x, cam_pos_y = cam.get_mean_centroid(self.SAMPLES)
            if np.isnan(cam_pos_x) or np.isnan(cam_pos_y):
                sleep(1)
                cam_pos_x, cam_pos_y = cam.get_mean_centroid(self.SAMPLES)
            cam_movement_x = target[0] - cam_pos_x
            if np.abs(cam_movement_x) < self.ALIGNMENT_THRESHOLD:
                cam_movement_x = 0
            cam_movement_y = target[1] - cam_pos_y
            if np.abs(cam_movement_y) < self.ALIGNMENT_THRESHOLD:
                cam_movement_y = 0
            # logger.log('pos: ', cam_pos_x, cam_pos_y)
            # logger.log('tar: ', target[0], target[1])
            # logger.log('mov: ', cam_movement_x, cam_movement_y)
            cam_offsets.append(cam_movement_x)
            cam_offsets.append(cam_movement_y)

        motor_movements = self.mm @ cam_offsets * self.GAIN

        for m_channel, motor_movement in zip(self.MOTOR_CHANNELS, motor_movements):
            if np.abs(motor_movement) > self.MOVEMENT_THRESHOLD:
                logger.log(f'WARNING: motor {m_channel} movement too large: {motor_movement}')
                return
        for m_channel, motor_movement in zip(self.MOTOR_CHANNELS, motor_movements):
            self.__move_rel(m_channel, motor_movement)

    def zero_all(self):
        for m_channel in self.MOTOR_CHANNELS:
            self.__move_abs(m_channel, 0)

if __name__ == "__main__":
    logger = customLogger('test.log')    
    parser = argparse.ArgumentParser()
    parser.add_argument("-A", "--acquire", dest='acquire', help="Begin to acquire motion matrix on start up", action='store_true')
    parser.add_argument("-Z", '--zero', dest='zero', help='Zero motors on start up', action='store_true')
    parser.add_argument("-M", '--motion-matrix', dest = 'mm', help='File name of the motion matrix to load', type=str)
    parser.add_argument('-G', '--gain', dest='gain', help='Uniform level of gain to apply on stabilization', default=0.004)
    parser.add_argument('-N', '--no-run', dest='no_run', help='Only open GUI, do not apply stabilization', action='store_false')
    args = parser.parse_args()
    sg = None #load nothing by default
    if args.acquire:
        if args.mm is not None:
            raise StarGuideError("Cannot set acquire==True and also provide motion matrix.")
        sg = StarGuide(debug=True)
        sleep(3)
        if args.zero:
            sg.zero_all()
            sleep(5)
        sg.acquire_motion_matrix(n_samples=1)
        np.save('motion_matrix.npy', sg.mm)
    if args.mm is not None:
        mm = np.load(args.mm)
        sg = StarGuide(motion_matrix=mm, debug=True)
        logger.log(mm)
        if args.zero:
            sg.zero_all()
            sleep(5)

    try:
        if sg is None:
            sg = StarGuide(debug=True) #load it if not loaded already, what happens when no input args provided
        sleep(3)
    except KeyboardInterrupt:
        sys.exit(2)
    if not args.no_run:
        sg.GAIN = args.gain
        sg.run()
        while True:
            try:
                sleep(0.1)
            except KeyboardInterrupt:
                sg.stop() 
                sys.exit(0)
