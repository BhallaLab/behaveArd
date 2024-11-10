import curses
import struct
import serial
import time
import numpy as np
import argparse
import datetime

IN_DATA_LEN = 10 # bytes
TIMEOUT = 1.1
STARTFLAG = 0x9876
BAUDRATE = 9600
PORT = "/dev/ttyUSB0"  # Replace with your Arduino's port
HEADERS = ["Time", "Stat", "LagT", "TR0", "TR1", "S2P", "Lite", "Tone", "Odd", "BG ", "Puff", "2p ", "Camr", "Trial"]

FIELDS = {
    "Trial number": 0,
    "State": "Initial",
    "Score": 0,
    "Elapsed Time": 0,
    "Status": "Ready",
    "Protocol": "sound"
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
    #return [protocol_state, time_elapsed_in_loop, millis_value, digital_values = [tread0, tread1, sync2p, light, toneCpy, ob_LED, bg_LED, uscope, puff, camera]]
    """
    numDigitalInputs = 11
    assert( len( data ) >= (IN_DATA_LEN - 1) )
    protocol_state = int(data[0])
    digital_values = int.from_bytes(data[1:3], byteorder='little')
    time_elapsed_in_loop = int.from_bytes(data[3:5], byteorder='little')
    millis_value = int.from_bytes(data[5:9], byteorder='little')
    #return "D", digital_values, trial_num, expt_state, protocol_state, time_elapsed_in_loop, millis_value
    digitalInputs = [millis_value, protocol_state, time_elapsed_in_loop]
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
    # Clear the line below the data.
    if len(data) < MAX_ROWS:
        stdscr.addstr(len(data)+2, 0, " " * curses.COLS)  
    xoff = 3

    # Print headers
    for i, header in enumerate(HEADERS):
        if i == 0:
            stdscr.addstr(1, i * 8, header, curses.A_BOLD)
        else:
            stdscr.addstr(1, xoff+i*5, header, curses.A_BOLD)

    # Print data rows
    for i, row in enumerate(data[-MAX_ROWS:]):  # Display most recent MAX_ROWS
        for j, val in enumerate(row):
            if j == 0:  # Shorts
                stdscr.addstr(i+2, j * 8, str(val).ljust(9))
            elif j < 3: #Shorts
                stdscr.addstr(i+2, xoff+j*5, str(val).ljust(4))
            else:  # Flags
                stdscr.addstr(i+2, xoff + j*5, " " * 5)  # Clear the block
                if val:
                    stdscr.addstr(i+2, xoff + j*5, " " * 4, curses.A_REVERSE)  # Filled block
                else:
                    stdscr.addstr(i+2, xoff + j*5, " " * 4)  # Empty block

def draw_fields(stdscr):
    for i, (key, value) in enumerate(FIELDS.items()):
        stdscr.addstr(MAX_ROWS + 4 + i, 0, f"{key}: {value}")
    stdscr.addstr(MAX_ROWS+4 + i+1, 0, "Spacebar to pause, q to quit")

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

def runTrial( currTrial, stdscr, arduino ):
    global FIELDS
    contents = []
    running = True
    paused = False
    while running:
        key = stdscr.getch()
        if key == ord('q'):
            FIELDS["Status" ] = "Halted"
            return 1, contents
        if key == ord(' '):
            paused = not paused
            FIELDS["Status"] = "Paused" if paused else "Running"
            draw_fields( stdscr )
            stdscr.refresh()
            time.sleep( 0.5 )
            #draw_full_line( 0, stdscr )
        if paused:
            continue
        data = arduinoRead(arduino)
        if data:
            ret = decodeIncomingData( data )
            contents.append(ret)  # Put in the data
            draw_table( contents, stdscr )
            FIELDS["Elapsed Time" ] = ret[0]/1000
            FIELDS["State" ] = ret[1]
            draw_fields( stdscr )
            stdscr.refresh()
            if ret[-1] == 0:
                return 0, contents


def fillProbes( args ):
    isProbe = innerFillProbes( args )
    while sum( isProbe ) != (args.numTrials // args.probeTrialSpacing):
        isProbe = innerFillProbes( args )
    return isProbe

def innerFillProbes( args ):
    lastProbe = 0
    # numProbes / numAvailSlots
    numProbes = args.numTrials // args.probeTrialSpacing
    newProbeProb = numProbes / (args.numTrials - numProbes * args.probeTrialMinSpacing )
    isProbe = np.zeros( args.numTrials, dtype=int )
    numActualProbes = 0
    for ii in range(args.numTrials):
        if ii > lastProbe+args.probeTrialMinSpacing:
            if np.random.rand() < newProbeProb and numActualProbes < numProbes:
                isProbe[ii] = 1
                lastProbe = ii
                numActualProbes += 1
    return isProbe

def runTEC( stdscr, arduino, args ):
    global FIELDS
    isProbe = fillProbes( args )

    trialRet = []
    for currTrial in range( args.numTrials ):
        FIELDS["Trial number"] = currTrial
        ptcl = FIELDS["Protocol"]
        if isProbe[currTrial]:
            if ptcl == "sound" or (ptcl == "multics" and (currTrial % args.probeTrialGap) == 0):
                arduinoSend(arduino, paramIdx["PROTOCOL"], SOUNDPROBE )
            elif FIELDS["Protocol"] == "light" or (ptcl == "multics" and (currTrial % args.probeTrialGap) == 1):
                arduinoSend(arduino, paramIdx["PROTOCOL"], LIGHTPROBE )
        else:
            if ptcl == "sound" or (ptcl == "multics" and (currTrial % args.probeTrialGap) == 0):
                arduinoSend(arduino, paramIdx["PROTOCOL"], SOUNDTRACE )
            elif ptcl == "light" or (ptcl == "multics" and (currTrial % args.probeTrialGap) == 1):
                arduinoSend(arduino, paramIdx["PROTOCOL"], LIGHTTRACE )
        arduinoSend(arduino, paramIdx["RUNCONTROL"], START )
        flag, contents = runTrial( currTrial, stdscr, arduino )
        if flag == 0: # Ended trial OK
            trialRet.append( contents )
            '''
            contentBlock = len( contents) + 1
            tc = [[0] * len( HEADERS )] * contentBlock
            for idx, cc in enumerate( contents ):
                if (idx+contentBlock) < MAX_ROWS:
                    tc.append( cc )
            draw_table( tc, stdscr )
            '''
            #draw_full_line( 1, stdscr )
            FIELDS["Status" ] = "Running"
            draw_fields( stdscr )
            stdscr.refresh()
        else:
            FIELDS["Status" ] = "Halted"
            break;
    if flag == 0:
        FIELDS["Status" ] = "Finished"
    draw_fields( stdscr )
    stdscr.refresh()
    return trialRet

def runGap( stdscr, arduino ):
    global FIELDS
    numTrials = 2
    trialRet = []
    for currTrial in range( numTrials ):
        oddball = int( np.random.rand() * 4 + 3 )
        FIELDS["Trial number"] = currTrial
        arduinoSend(arduino, paramIdx["OBPOS"], 10 + oddball )
        arduinoSend(arduino, paramIdx["RUNCONTROL"], START )
        flag, contents = runTrial( currTrial, stdscr, arduino )
        if flag == 0: # Ended trial OK
            trialRet.append( contents )
            #draw_full_line( 1, stdscr )
            FIELDS["Status" ] = "Running"
            draw_fields( stdscr )
            stdscr.refresh()
        else:
            FIELDS["Status" ] = "Halted"
            break;
    if flag == 0:
        FIELDS["Status" ] = "Finished"
    draw_fields( stdscr )
    stdscr.refresh()
    return trialRet


def main():
    global FIELDS
    ''' This program controls an arduino which performs precise timing for
    a mouse behavioural protocol. There is also an ncurses interface to see
    what is going on with the hardware events and the animal's movement.
    '''
    parser = argparse.ArgumentParser( description = 'behave.py: A program to control mouse behaviour on arduino.' )
    parser.add_argument('-f', '--file', type = str, help = "Optional: Specify output filename. Default: out_yyyymmdd_tt.txt.", default = None )
    parser.add_argument('-p', '--protocol', type = str, help = "Optional: Specify which protocol of light, sound, multics or oddball. Default: sound.", default = "sound" )
    parser.add_argument('-n', '--numTrials', type = int, help = "Optional: How many trials to run. Default: 60.", default = 60 )
    parser.add_argument('-ps', '--probeTrialSpacing', type = int, help = "Optional: Mean spacing between as probe trials. Default: 10.", default = 10 )
    parser.add_argument('-pm', '--probeTrialMinSpacing', type = int, help = "Optional: Minimum number of trials between probe trials. Default: 6.", default = 6 )
    args = parser.parse_args()

    FIELDS["Protocol"] = args.protocol
    if args.protocol == "oddball":
        protocolParms = OddballParms
    elif args.protocol in ["light", "sound", "multics"]:
        protocolParms = dict(TECParms)
    else:
        print("Behaviour protocol ", args.protocol, " not known. Quitting.")
        quit()

    arduino = initArduino( protocolParms )
    stdscr = initCurses()

    if args.protocol == "oddball":
        trialRet = runGap( stdscr, arduino )
    else:
        trialRet = runTEC( stdscr, arduino, args )
    ############### Go into control mode #################
    running = True
    while running:
        key = stdscr.getch()
        if key == ord('q'):
            running = False
        time.sleep( 0.5 )

    ############### Clean up after #################
    curses.endwin()

    now = datetime.datetime.now()
    # Format the date and time as yyyymmdd_tt
    date_time_string = now.strftime("%Y%m%d_%H%M")  # %H for 24-hour format
    filename = args.file if args.file else f"out_{date_time_string}.txt"
    with open(filename, 'w') as file:
        file.write( "Trial\tevent" )
        for hh in HEADERS:
            file.write( "\t"+hh )
        for idx, tt in enumerate( trialRet ):   # Go through all trials
            for idx2, ee in enumerate( tt ):    # Go through all events
                file.write( "\n"+ str( idx )+ "\t"+ str( idx2 ) )
                for cc in ee:                   # Go through all fields
                    file.write( "\t"+ str(cc) )
        # Write a line to the file
        file.write("\n")
        #file.write("This is a line of text.\n")

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
