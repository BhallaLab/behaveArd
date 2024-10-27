import curses
import struct
import serial
import time
import argparse

IN_DATA_LEN = 10 # bytes
TIMEOUT = 1.1
STARTFLAG = 0x9876
BAUDRATE = 9600
PORT = "/dev/ttyUSB0"  # Replace with your Arduino's port
HEADERS = ["State  ", "Loop T ", "Total T", "TR0", "TR1", "LED", "TON", "Odd", "BG ", "Ton", "Puf ", "2p ", "CaM "]
FIELDS = {
    "Trial number": 0,
    "State": "Initial",
    "Score": 0,
    "Elapsed Time": 0,
    "Status": "Ready"
}
MAX_ROWS = 15

def connect_to_arduino(port, baudrate):
    try:
        ser = serial.Serial(port, baudrate)
        print(f"Connected to Arduino on port {port}")
        return ser
    except serial.SerialException as e:
        print(f"Error connecting to Arduino: {e}")
        return None

def arduinoSend( ser, key, value ):
    # This is a blocking call, Keepts trying till TIMEOUT or success
    shorts = [STARTFLAG, key, value]
    packed_data = struct.pack('<HHH', *shorts)
    t0 = time.time()
    while (time.time() - t0) < TIMEOUT:
        ser.write(packed_data)
        time.sleep( 0.05 )
        while ser.in_waiting:  # Check for ack
            ret = ser.read()
            #print( "RET = ", ret )
            if ret == b'R':
                time.sleep( 0.05 )
                return
    print( "TIMEOUT on arduinoSend. Bad news. Quitting." )
    quit()

def arduinoRead(ser):
    # This is a blocking call. Waits till TIMEOUT
    if ser.in_waiting > 0:
        ret = ser.read()
        if ret == b'D': # This is a data packet
            try:
                data = ser.read( IN_DATA_LEN-1 ) 
                #print( "GOT all DATA TYPE D", flush=True )
                return data
            except serial.SerialTimeoutException:
                print( "FAILED serial read", flush = True )
        elif ret == b'R': # This is an ack package saying data received
            return None
        else:
            print( "bad return ", ret )
    return None

def decodeIncomingData(data):
    """
    Decodes the digital input values from the received data.
    Args: data: The received data as a bytes_array.
    Data contents: ['D', protocolState, digitalValues, millis ]
    #return [protocol_state, time_elapsed_in_loop, millis_value, digital_values = [tread0, tread1, light, toneCpy, ob_LED, bg_LED, tone, uscope, puff, camera]]
    """
    numDigitalInputs = 11
    assert( len( data ) >= (IN_DATA_LEN - 1) )
    protocol_state = int(data[0])
    digital_values = int.from_bytes(data[1:3], byteorder='little')
    time_elapsed_in_loop = int.from_bytes(data[3:5], byteorder='little')
    millis_value = int.from_bytes(data[5:9], byteorder='little')
    #return "D", digital_values, trial_num, expt_state, protocol_state, time_elapsed_in_loop, millis_value
    digitalInputs = [protocol_state, time_elapsed_in_loop, millis_value]
    for i in range(numDigitalInputs):
        digitalInputs.append((digital_values >> i) & 1)
    return digitalInputs

GAP = int(0)
SOUNDTRACE = int(1)
SOUNDPROBE = int(2)
LIGHTTRACE = int(3)
LIGHTPROBE = int(4)
MULTITRACE = int(5)
MULTISOUND = int(6)
MULTILIGHT = int(7)

STOP = int(0)
START = int(1)
CONTINUE = int(2)
RESET = int(3)

# Protocols are GAP, SOUNDTRACE, LIGHTTRACE, MULTICS etc
# RUNCONTROL can be START, STOP, CONTINUE, RESET
params = ["RUNCONTROL", "PROTOCOL", "RECORDSTART", "RECORDDUR", "TDUR", 
    "INITDELAY", "BGFREQ", "OBFREQ", "BGDUR", "OBDUR", "OBPOS", "PUFFDUR",
    "ISI", "ITI", "TONENUMS", "UPDATEINTERVAL"]
paramIdx = { pp:idx for idx, pp in enumerate( params )}

TECParms = {
        "PROTOCOL": SOUNDTRACE, "RECORDSTART": 500, "RECORDDUR": 1000, 
        "TDUR": 2500, "INITDELAY": 1000, 
        "BGFREQ": 5000, "OBFREQ": 1000, "BGDUR": 50, "OBDUR":50, "OBPOS":6,
        "PUFFDUR": 50, "ISI": 250, "ITI": 1000, 
        "TONENUMS": 1, "UPDATEINTERVAL": 2
}

OddballParms = {
        "PROTOCOL": GAP, "RECORDSTART": 10000, "RECORDDUR": 10000, 
        "TDUR": 20000, "INITDELAY": 500, 
        "BGFREQ": 5000, "OBFREQ": 1000, "BGDUR": 50, "OBDUR":50, "OBPOS":16,
        "PUFFDUR": 50, "ISI": 1000, "ITI": 1000, 
        "TONENUMS": 20, "UPDATEINTERVAL": 2
}

# Contents of values from Arduino. 10 bytes if data, else 1 byte.
# byte 0: Type of data. Either D for data, R for received, or E for error.
# byte 1: Protocol state. One of PRE, CS, TRACE, US, POST, ODDBALL.
# byte 2,3: State of all digital inputs, also state of isTrial in bit 11.
# byte 4,5: Time elapsed in loop, in ms.
# byte 6-9: millis.

#########################################################################
# Curses stuff below
#########################################################################
def draw_table(data, stdscr):
    # Calculate starting row for table based on current data size
    stdscr.addstr(MAX_ROWS, 0, " " * curses.COLS)  # Clear the line above the table

    # Print headers
    for i, header in enumerate(HEADERS):
        if i < 3:
            stdscr.addstr(1, i * 10, header, curses.A_BOLD)
        else:
            stdscr.addstr(1, 15+i*5, header, curses.A_BOLD)

    # Print data rows
    for i, row in enumerate(data[-MAX_ROWS:]):  # Display only the last MAX_ROWS
        for j, val in enumerate(row):
            if j < 3:  # Shorts
                stdscr.addstr(i+2, j * 10, str(val).ljust(9))
            else:  # Flags
                stdscr.addstr(i+2, 15+ j * 5, " " * 5)  # Clear the block
                if val:
                    stdscr.addstr(i+2, 15+ j * 5, " " * 5, curses.A_REVERSE)  # Filled block
                else:
                    stdscr.addstr(i+2, 15+ j * 5, " " * 5)  # Empty block

def draw_fields(fields, stdscr):
    for i, (key, value) in enumerate(fields.items()):
        stdscr.addstr(MAX_ROWS + 3 + i, 0, f"{key}: {value}")
    stdscr.addstr(MAX_ROWS+3 + i, 0, "Spacebar to pause, q to quit")

def draw_full_line( color, stdscr ):
    if color == 0:
        stdscr.addstr(MAX_ROWS + 2, 0, " " * 80)
    else:
        stdscr.addstr(MAX_ROWS + 2, 0, " " * 80,
            curses.A_REVERSE | curses.color_pair(color))

#################################################################

def initCurses():
    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    curses.curs_set(0)  # Hide cursor
    stdscr.nodelay(True)  # Non-blocking input
    stdscr.clear()
    curses.start_color()
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    return stdscr

def initArduino( protocolParms ):
    arduino = connect_to_arduino(PORT, BAUDRATE)
    if not arduino:
        print( "Failed to open arduino. Quitting.")
        quit()
    arduino.flushInput()  # Flush the input buffer
    arduino.reset_input_buffer()  # Flush the input buffer
    arduino.reset_output_buffer()  # Flush the output buffer
    
    for key, val in protocolParms.items():
        arduinoSend( arduino, paramIdx[key], val )
    print( "SENT ALL PARAMS", flush = True )
    time.sleep(1)
    return arduino

def runTrial( currTrial, stdscr, arduino, fields ):
    contents = []
    running = True
    while running:
        key = stdscr.getch()
        if key == ord('q'):
            return 1, contents
        if key == ord(' '):
            draw_full_line( 2, stdscr )
            stdscr.refresh()
            time.sleep( 0.5 )
            draw_full_line( 0, stdscr )
        data = arduinoRead(arduino)
        if data:
            ret = decodeIncomingData( data )
            contents.append(ret)  # Put in the data
            draw_table( contents, stdscr )
            fields["Elapsed Time" ] = ret[2]/1000
            fields["State" ] = ret[1]
            fields["Status" ] = "Running"
            draw_fields( fields, stdscr )
            stdscr.refresh()
            #print( ret )
            if ret[-1] == 0:
                return 0, contents

def main():
    ''' This program controls an arduino which performs precise timing for
    a mouse behavioural protocol. There is also an ncurses interface to see
    what is going on with the hardware events and the animal's movement.
    '''
    parser = argparse.ArgumentParser( description = 'behave.py: A program to control mouse behaviour on arduino.' )
    parser.add_argument('-p', '--protocol', type = str, help = "Optional: Specify which protocol of light, sound, multics or oddball. Default: sound.", default = "sound" )
    args = parser.parse_args()


    if args.protocol == "oddball":
        protocolParms = OddballParms
        numTrials = 1
        probeTrial = -1
    else:
        protocolParms = dict(TECParms)
        numTrials = 5
        probeTrial = 3
        if args.protocol == "light":
            protocolParms["PROTOCOL"] = LIGHTTRACE
        if args.protocol == "sound":
            protocolParms["PROTOCOL"] = SOUNDTRACE
        if args.protocol == "multics":
            protocolParms["PROTOCOL"] = MULTITRACE

    arduino = initArduino( protocolParms )
    stdscr = initCurses()

    currTrial = 0
    trialRet = []

    fields = {
        "Trial number": 0,
        "State": "Initial",
        "Score": 0,
        "Elapsed Time": 0,
        "Status": "Ready"
    }

    arduinoSend(arduino, paramIdx["RUNCONTROL"], START )
    for currTrial in range( numTrials ):
        fields["Trial number"] = currTrial
        flag, contents = runTrial( currTrial, stdscr, arduino, fields )
        if flag == 0: # Ended trial OK
            trialRet.append( contents )
            draw_full_line( 1, stdscr )
            if currTrial < numTrials:
                fields["Status" ] = "Running"
                if currTrial == probeTrial:
                    arduinoSend(arduino, paramIdx["PROTOCOL"], SOUNDPROBE )
                else:
                    arduinoSend(arduino, paramIdx["PROTOCOL"], SOUNDTRACE )
                #time.sleep( 0.1 )
                arduinoSend(arduino, paramIdx["RUNCONTROL"], START )
                #time.sleep( 0.1 )
            else:
                fields["Status" ] = "Finished"
        else:
            fields["Status" ] = "Halted"
            break;

    draw_fields( fields, stdscr )
    stdscr.refresh()
    ############### Go into control mode #################
    running = True
    while running:
        key = stdscr.getch()
        if key == ord('q'):
            running = False
        time.sleep( 0.5 )

    ############### Clean up after #################
    curses.endwin()

if __name__ == "__main__":
    main()

'''
def display_data(stdscr, digital_inputs, analog_inputs):
    stdscr.clear()
    stdscr.addstr(1, 1, "Digital Inputs:")
    for i, value in enumerate(digital_inputs):
        stdscr.addstr(2 + i, 1, f"Input {i+1}: {value}")
    stdscr.addstr(1, 30, "Analog Inputs:")
    for i, value in enumerate(analog_inputs):
        stdscr.addstr(2 + i, 30, f"Input {i+1}: {value}")
    stdscr.refresh()
'''
