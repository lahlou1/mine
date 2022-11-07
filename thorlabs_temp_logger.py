import os
import ctypes as C


class Data_Logger:
    # stolen from https://github.com/amsikking/thorlabs_TSP01B
    '''
    Basic device adaptor for Thorlabs TSP01B USB Temperature and Humidity Data
    Logger, Including External Temperature Probes, -15 °C to 200 °C. Many more
    commands are available and have not been implemented.
    Note:
    - written and tested for "TSP01 RevB Sensors"
    - also works for multiple devices
    '''
    def __init__(self, name='TSP01B', devices=1, verbose=True):
        self.name = name
        self.verbose = verbose
        self.channel_name_to_number  = {'Main':11, 'TH1':12, 'TH2':13}
        if self.verbose: print("%s: opening..."%self.name)
        device_count = C.c_uint32()
        dll.get_device_count(0, device_count)
        assert device_count.value == devices
        self.device_number_to_handle = {}
        for device in range(devices):
            device_name = (256 * C.c_char)()
            dll.get_device_name(0, device, device_name)
            device_handle = C.c_uint32()
            dll.get_device_handle(device_name, 0, 0, device_handle)
            self.device_number_to_handle[device] = device_handle
            if self.verbose:
                print("%s(%i): device name   = %s"%(
                    self.name, device, device_name.value.decode('ascii')))
                print("%s(%i): device number = %s"%(
                    self.name, device, device))
            self.get_device_info(device)
        if self.verbose: print("%s: opened and ready.\n"%self.name)

    def _reset(self):
        if self.verbose: print("%s: reseting..."%self.name, end='')
        for device in self.device_number_to_handle:
            dll.reset(self.device_number_to_handle[device])
        if self.verbose: print(" done.")

    def get_device_info(self, device=0):
        assert device in self.device_number_to_handle
        device_handle = self.device_number_to_handle[device]
        if self.verbose:
            print("%s(%i): device info;"%(self.name, device))
        model         = (256 * C.c_char)()
        serial_number = (256 * C.c_char)()
        manufacturer  = (256 * C.c_char)()
        in_use        = C.c_bool()
        dll.get_device_info(
            device_handle, device, model, serial_number, manufacturer, in_use)
        if self.verbose:
            print("%s(%i):  - model         = %s"%(
                self.name, device, model.value.decode('ascii')))
            print("%s(%i):  - serial_number = %s"%(
                self.name, device, serial_number.value.decode('ascii')))
            print("%s(%i):  - manufacturer  = %s"%(
                self.name, device, manufacturer.value.decode('ascii')))
            print("%s(%i):  - in_use        = %s"%(
                self.name, device, in_use.value))
        return model, serial_number, manufacturer, in_use

    def get_humidity(self, device=0):
        assert device in self.device_number_to_handle
        device_handle = self.device_number_to_handle[device]
        if self.verbose:
            print("%s(%i): getting humidity"%(self.name, device))
        humidity = C.c_double()
        dll.get_humidity(device_handle, humidity)
        humidity = humidity.value
        if self.verbose:
            print("%s(%i):  = %10.06f"%(self.name, device, humidity))
        return humidity

    def get_temperature(self, channel_name, device=0):
        assert device in self.device_number_to_handle
        device_handle = self.device_number_to_handle[device]
        assert channel_name in self.channel_name_to_number, (
            "channel '%s' not found"%channel_name)
        channel = self.channel_name_to_number[channel_name]
        if self.verbose:
            print("%s(%i): getting temperature (channel=%s)"%(
                self.name, device, channel_name))
        temperature = C.c_double()
        dll.get_temperture(device_handle,
                           channel,
                           temperature)
        temperature = temperature.value
        if self.verbose:
            print("%s(%i):  = %10.06f"%(self.name, device, temperature))
        return temperature

    def close(self):
        if self.verbose: print("%s: closing..."%self.name, end='')
        for device in self.device_number_to_handle:
            dll.close(self.device_number_to_handle[device])
        if self.verbose: print(" done.")
        return None

### Tidy and store DLL calls away from main program:

os.add_dll_directory(os.getcwd())
dll = C.cdll.LoadLibrary("TLTSPB_64") # needs "TLTSPB_64.dll" in directory

dll.get_error_message = dll.TLTSPB_errorMessage
dll.get_error_message.argtypes = [
    C.c_uint32,                 # instrumentHandle
    C.c_uint32,                 # statusCode
    C.c_char_p]                 # description[]
dll.get_error_message.restype = C.c_uint32

def check_error(error_code):
    if error_code != 0:
        print("Error message from Thorlabs TSP01B: ", end='')
        error_message = (512 * C.c_char)()
        dll.get_error_message(0, error_code, error_message)
        print(error_message.value.decode('ascii'))
        raise UserWarning(
            "Thorlabs TSP01B error: %i; see above for details."%(error_code))
    return error_code

dll.get_device_count = dll.TLTSPB_findRsrc
dll.get_device_count.argtypes = [
    C.c_uint32,                 # instrumentHandle
    C.POINTER(C.c_uint32)]      # deviceCount
dll.get_device_count.restype = check_error

dll.get_device_name = dll.TLTSPB_getRsrcName
dll.get_device_name.argtypes = [
    C.c_uint32,                 # instrumentHandle
    C.c_uint32,                 # deviceIndex
    C.c_char_p]                 # resourceName[]
dll.get_device_name.restype = check_error

dll.get_device_handle = dll.TLTSPB_init
dll.get_device_handle.argtypes = [
    C.c_char_p,                 # resourceName
    C.c_bool,                   # IDQuery
    C.c_bool,                   # resetDevice
    C.POINTER(C.c_uint32)]      # instrumentHandle
dll.get_device_handle.restype = check_error

dll.reset = dll.TLTSPB_reset
dll.reset.argtypes = [
    C.c_uint32]                 # instrumentHandle
dll.reset.restype = check_error

dll.get_device_info = dll.TLTSPB_getRsrcInfo
dll.get_device_info.argtypes = [
    C.c_uint32,                 # instrumentHandle
    C.c_uint32,                 # deviceIndex
    C.c_char_p,                 # modelName
    C.c_char_p,                 # serialNumber
    C.c_char_p,                 # manufacturerName
    C.POINTER(C.c_bool)]        # resourceInUse
dll.get_device_info.restype = check_error

dll.get_humidity = dll.TLTSPB_measHumidity
dll.get_humidity.argtypes = [
    C.c_uint32,                 # instrumentHandle
    C.POINTER(C.c_double)]      # humidityValue
dll.get_humidity.restype = check_error

dll.get_temperture = dll.TLTSPB_measTemperature
dll.get_temperture.argtypes = [
    C.c_uint32,                 # instrumentHandle
    C.c_uint16,                 # channel
    C.POINTER(C.c_double)]      # temperatureValue
dll.get_temperture.restype = check_error

dll.close = dll.TLTSPB_close
dll.close.argtypes = [
    C.c_uint32]                 # instrumentHandle
dll.restype = check_error

if __name__ == '__main__':
    from datetime import datetime, timezone
    from time import sleep
    import mysql.connector
    from mysql.connector.errors import IntegrityError

    logger = Data_Logger(verbose=False)
    connection = mysql.connector.connect(host='132.206.175.136', user='logger', password='diffraction')
    cursor = connection.cursor()
    cursor.execute('USE logging')

    while True:
        try:
            ts = datetime.now() - datetime.now().astimezone().utcoffset()
            if ts.second == 0:
                t0 = logger.get_temperature('Main')
                t1 = logger.get_temperature('TH1')
                h = logger.get_humidity()
                try:
                    cursor.execute(
                        f"INSERT INTO AMBIENT(TIMESTAMP, TEMPERATURE_0, TEMPERATURE_1, HUMIDITY) VALUES ('{ts}', {t0}, {t1}, {h})"
                        )
                    connection.commit()
                except IntegrityError as e:
                    pass
            sleep(0.9)
        except Exception as e:
            break

    logger.close()
