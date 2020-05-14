import serial
import serial.tools.list_ports

from libs import Logger

class SerialPort():

    @Logger.function_log
    def __init__(self,
                 port=None,
                 baudrate=115200,
                 bytesize=8,
                 parity='N',
                 stopbits=1,
                 timeout=1,
                 xonxoff=0,
                 rtscts=0):

        self.port = port
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.timeout = timeout
        self.xonxoff = xonxoff
        self.rtscts = rtscts

        self.serial = serial.Serial(self.port,
                                    self.baudrate,
                                    self.bytesize,
                                    self.parity,
                                    self.stopbits,
                                    self.timeout,
                                    self.xonxoff,
                                    self.rtscts)

        self.resource_free = True
        self.connection_active = True
        self.port_release = True


    @Logger.function_log
    def send(self, *args, **kwargs):
        '''
        Send command to serial port if resource is not currently in use and wait for reply.
        :param cmd: hardware command
        :param progress_callback: signal handler (unused currently)
        :return:
        '''

        self.command = kwargs['command']
        self.resource_free = False

        while self.port_release == False:  # Wait for Listen to release resource
            pass

        try:
            bytes = self.serial.write('{cmd}\n'.format(cmd=self.command).encode())
            self.resource_free = True

            return bytes
        except serial.serialutil.SerialException:
            print('Read failed.')

    @Logger.function_log
    def read(self):
        '''
        Read serial port for incoming data and passes it to decoding function via progress_callback signal.
        :param progress_callback: Generates a signal to pass data to the decoding function from within the thread.
        :return: None
        '''
        try:
            if self.resource_free:
                self.port_release = False
                line = self.serial.read_until().decode().rstrip()
#                progress_callback.emit(line)
                self.port_release = True

                return line
            else:
                pass
        except serial.serialutil.SerialException:
            print('Read error occurred.')

    @Logger.function_log
    def listen(self, progress_callback):
        '''
        Monitors serial port for incoming data and passes it to decoding function via progress_callback signal.
        :param progress_callback: Generates a signal to pass data to the decoding function from within the thread.
        :return: None
        '''

        print('Listening on {port}'.format(port=self.port))
        while self.connection_active:
            try:
                if self.serial.inWaiting() and self.resource_free:
                    self.port_release = False
                    self.serial.flush()
                    line = self.serial.readline().decode()
                    print("Response check: {resp}".format(resp=line))
                    progress_callback.emit(line)
                    self.port_release = True
                else:
                    pass
            except serial.serialutil.SerialException:
                print('Listening error occurred.')

    @Logger.function_log
    def _is_open(self):
        '''
        Passes boolean depending on state of serial connection
        :return: serial port connection state *True/False)
        '''

        return self.serial.is_open

    @Logger.function_log
    def disconnect(self):
        '''
        Close serial port connection.
        :return: None
        '''

        self.resource_free = False
        self.connection_active = False
        self.serial.close()