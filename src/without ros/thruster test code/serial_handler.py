import serial
import threading
import time

PACKET_START = 0xAC
PACKET_END = 0xAD
PACKET_ESCAPE = 0xAE
PACKET_ESCAPE_MASK = 0x80

REMOTE_ADDRESS = 0x14
DISPLAY_ADDRESS = 0x20
PORT = 'COM4'
BAUDRATE = 19200
TICKS_PER_REV = 2048

# Shared data for GUI
shared_data = {
    "rpm": 0,
    "power": 0,
    "battery": 0,
    "throttle": 0
}
data_lock = threading.Lock()

# Internal state
first_byte_received = False
in_a_message = False
next_byte_is_address = False
remote_display_msg_received = False
global_start_time = 0.0

def crc8(data: bytes) -> int:
    crc = 0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x01:
                crc = (crc >> 1) ^ 0x8C
            else:
                crc >>= 1
    return crc

def escape_bytes(data):
    out = []
    for byte in data:
        if byte in (PACKET_START, PACKET_END, PACKET_ESCAPE):
            out.extend([PACKET_ESCAPE, byte ^ PACKET_ESCAPE_MASK])
        else:
            out.append(byte)
    return out

def make_slave_response(msg_id, body):
    payload = [0x00, msg_id] + body
    payload.append(crc8(payload))
    escaped = escape_bytes(payload)
    return bytes([PACKET_START] + escaped + [PACKET_END])

def int16_to_bytes(val):
    if val < 0:
        val = (1 << 16) + val
    return [(val >> 8) & 0xFF, val & 0xFF]

def get_14_message_body():
    if time.time() - global_start_time < 3.9:
        return [0x01, 0x00, 0x00, 0x00]
    else:
        with data_lock:
            throttle = shared_data["throttle"]
        packed = int16_to_bytes(throttle)
        return [0x05, 0x00, packed[0], packed[1]]

def serial_loop():
    global first_byte_received, in_a_message, next_byte_is_address, remote_display_msg_received, global_start_time

    try:
        ser = serial.Serial(
            port=PORT,
            baudrate=BAUDRATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
            timeout=1.0
        )
        print(f"Connected to {PORT} at {BAUDRATE} baud")
    except Exception as e:
        print(f"Failed to open serial port: {e}")
        return

    buffer = bytearray()

    while True:
        byte = ser.read(1)
        if not byte:
            continue

        b = byte[0]
        buffer.append(b)

        if not first_byte_received:
            first_byte_received = True
            global_start_time = time.time()
            print("Listening on RS485 bus as 0x14 and 0x20 slave")

        if b == PACKET_END and in_a_message:
            in_a_message = False

        if next_byte_is_address:
            next_byte_is_address = False
            if b == REMOTE_ADDRESS or b == DISPLAY_ADDRESS:
                remote_display_msg_start_time = time.time()
                remote_display_msg_received = True
            else:
                remote_display_msg_received = False

        if b == PACKET_START and not in_a_message:
            in_a_message = True
            next_byte_is_address = True

        if not in_a_message and remote_display_msg_received:
            # Unescape payload
            payload = []
            i = 1
            while i < len(buffer) - 1:
                if buffer[i] == PACKET_ESCAPE:
                    i += 1
                    payload.append(buffer[i] ^ PACKET_ESCAPE_MASK)
                else:
                    payload.append(buffer[i])
                i += 1

            addr, msg_id = payload[1], payload[2]

            if addr == REMOTE_ADDRESS and msg_id == 0x01:
                time.sleep(0.00052)
                ser.rts = True
                body = get_14_message_body()
                reply = make_slave_response(0x00, body)
                ser.write(reply)
                ser.flush()
                print(f"Replied to REMOTE 0x01 with: {reply}")
                time.sleep(0.001)
                ser.rts = False

            elif addr == DISPLAY_ADDRESS and msg_id == 0x41:
                offset = 3
                speed_bytes = [payload[10+offset], payload[11+offset]]
                raw_speed = (speed_bytes[0] << 8) | speed_bytes[1]
                if raw_speed >= 0x8000:
                    speed_int = raw_speed - 0x10000
                else:
                    speed_int = raw_speed
                rpm = (speed_int / TICKS_PER_REV) * 60

                with data_lock:
                    shared_data["rpm"] = int(rpm)
                    shared_data["power"] = payload[8+offset]
                    shared_data["battery"] = payload[14+offset]

                print("Updated DISPLAY 0x41 data")

            buffer.clear()
            ser.rts = False
            remote_display_msg_received = False
