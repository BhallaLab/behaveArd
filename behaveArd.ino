//////////////////////////////////////////////////////////////////////////
//
//		This program is for the Bhalla Lab behaviour work for 
// gap conditioning and variants of trace-eyeblink conditioning.
// 
//  			Copyright (c) Upinder S. Bhalla and NCBS-TIFR 2024
//
// It is distributed under the terms of GPLv3.0
//
//////////////////////////////////////////////////////////////////////////

#define BAUDRATE 9600
// Here are the parameter indices to use in the dataTemp array
#define nParams 16
#define RUNCONTROL 0
#define PROTOCOL 1
#define RECORDSTART 2
#define RECORDDUR 3
#define TDUR 4		// Trial duration
#define INITDELAY 5
#define BGFREQ 6
#define OBFREQ 7
#define BGDUR 8
#define OBDUR 9
#define TONEDUR 8	// alias for BGDUR, used for TEC.
#define LIGHTDUR 9	// alias for OBDUR, used for TEC.
#define OBPOS 10
#define PUFFDUR 11
#define ISI 12		// Inter-stimulus interval. Also trace interval.
#define ITI 13		// Inter-trial Inteval
#define	TONENUMS 14
#define	UPDATEINTERVAL 15

#define STOP 0
#define START 1
#define CONTINUE 2
#define RESET 3

#define PROTOCOL_GAP 0
#define PROTOCOL_SOUNDTRACE 1
#define PROTOCOL_SOUNDPROBE 2
#define PROTOCOL_LIGHTTRACE 3
#define PROTOCOL_LIGHTPROBE 4
#define PROTOCOL_MULTITRACE 5
#define PROTOCOL_MULTISOUND 6
#define PROTOCOL_MULTILIGHT 7

#define STATE_PRE 0
#define STATE_CS 1
#define STATE_TRACE 2
#define STATE_US 3
#define STATE_POST 4
#define STATE_ODDBALL 5

// Output pin definitions
const int camera_pin = 12; 
const int scope_pin = 10; 
// const int shockpin = 13;  // Uncomment if shock pin is used
const int puffpin = 11;  	// Pin for airpuff
const int tonepin = 8;      // Pin for tone generation, also CS1
const int bg_LED = 7;       // LED for background stimulus
const int ob_LED = 6;       // LED for oddball stimulus
const int tone_copy = 5;    // Another output for tone, also CS1
const int lightpin = 4;  	// Pin for CS2
// INPUT PINS
const int tread0 = 2;
const int tread1 = 3;
const int sync2p = 9;

// Define pin numbers for digital inputs, analog inputs, and digital outputs
const int digitalInputs[] = {tread0, tread1, sync2p};
const int analogInputs[] = {A0, A1, A2};
const int digitalOutputs[] = {lightpin, tone_copy, ob_LED, bg_LED, puffpin, scope_pin, camera_pin};
const int allDigitalPins[] = {tread0, tread1, sync2p, lightpin, tone_copy, ob_LED, bg_LED, puffpin, scope_pin, camera_pin};
const int numPins  = sizeof( allDigitalPins ) / sizeof( allDigitalPins[0] );

// Here are a set of globals that define the experiment state
static byte protocolState = STATE_PRE;
static byte oldbytes[10];
static bool isTrial = false;
static unsigned long nextt = 0;


// The dataTemp array defines the experiment parameters
short dataTemp[nParams];

/////////////////////////////////////////////////////////////////////
// Function to read and print input values. Only sends if there is a change
void sendToHost( unsigned short timeElapsedInLoop ) {
	static byte oldbytes[10] = {0,0,0,0,0, 0,0,0,0,0};
	byte bytes[10];
	bytes[0] = 'D';
	bytes[1] = byte(protocolState - STATE_PRE);
	unsigned short* digitalValues = (unsigned short*)(bytes+2);
	*digitalValues = 0;
	// Digital pins 0 and 1 may be for tx and recv, use for isTrial flag
	if (isTrial)
		 *digitalValues |= 1 << numPins;
	for (int i = 0; i < numPins; i++) {
		*digitalValues |= digitalRead(allDigitalPins[i]) << i;
  	}
	*((unsigned short*)(bytes+4)) = timeElapsedInLoop;
	bool old = true;
	for ( int ii = 1; ii < 6; ++ii) {	// the 'D' is always the same.
		if (oldbytes[ii] != bytes[ii]) {
			old = false;
			oldbytes[ii] = bytes[ii];
		}
	}
	if (!old) { // Fill up the rest of the data and send it
		*((unsigned long*)(bytes+6)) = millis();
		Serial.write(bytes, 10);
	}
}

boolean recvFromHost( uint16_t* receivedShorts ) {
	unsigned short* temp;
	const unsigned short startFlag = 0x9876;
	// Track how many serial parameters have been received.
    // Check for serial input to update parameters
	// Expect 3 ushorts: Flag, ID of parameter, value. 6 bytes.
	if (Serial.available() >= 6) {
    	for (int i = 0; i < 3; i++) {
			receivedShorts[i] = Serial.read() | (Serial.read() << 8); 
		}
		if (receivedShorts[0] == startFlag) { // Check for valid magic#
			Serial.write( 'R' );		// Let sender know data came.
			return true;
		} else {
			Serial.write( 'E' );		// Let sender know Error.
		}
	}
	return false;
}

/////////////////////////////////////////////////////////////////////
// Functions for hardware control

void flashOnboardLED() {
  	digitalWrite(LED_BUILTIN, HIGH);
  	delay(50); // Wait for 0.2 second
  	digitalWrite(LED_BUILTIN, LOW);
  	delay(300); // Wait for 0.2 second
  	digitalWrite(LED_BUILTIN, HIGH);
  	delay(100); // Wait for 0.2 second
  	digitalWrite(LED_BUILTIN, LOW);
  	delay(100); // Wait for 0.2 second
  	digitalWrite(LED_BUILTIN, HIGH);
  	delay(100); // Wait for 0.2 second
  	digitalWrite(LED_BUILTIN, LOW);
  	delay(100); // Wait for 0.2 second
}

void killAllActiveDigitalLines() {
	noTone(tonepin);                // Stop the tone
	for (int i = 0; i < sizeof(digitalOutputs) / sizeof(digitalOutputs[0]); i++) {
		digitalWrite(digitalOutputs[i], LOW);    
  }
}

/////////////////////////////////////////////////////////////////////
// Here we encode the various protocols.

void gapProtocol( unsigned long dt ) {
	static bool lastTone = false;
	int numTone = int( dt / dataTemp[ISI] );
	int temp = int( (dt+dataTemp[BGDUR]) / dataTemp[ISI] );
	bool isToneOn = ( temp > numTone );
	bool isOddball = ((numTone==dataTemp[OBPOS]) && dataTemp[RECORDDUR]>0 );
	
	if ( isOddball ) {
		if (isToneOn && (isToneOn != lastTone)) {
        	digitalWrite(bg_LED, LOW);    // Turn off background LED
        	digitalWrite(ob_LED, HIGH);     // Turn on oddball LED
			noTone(tonepin);                // Stop the tone
        	digitalWrite(tone_copy, LOW); // Turn off tone copy
			protocolState = STATE_ODDBALL;
			lastTone = isToneOn;
		}
		if (!isToneOn && (isToneOn != lastTone)) {
      		digitalWrite(bg_LED, LOW);      // Turn off background LED
      		digitalWrite(ob_LED, LOW);      // Turn off oddball LED
			noTone(tonepin);                // Stop the tone
      		digitalWrite(tone_copy, LOW);   // Turn off tone copy
			protocolState = STATE_POST;
			lastTone = isToneOn;
		}
	} else {
		if (isToneOn && (isToneOn != lastTone)) {
        	digitalWrite(bg_LED, HIGH);    // Turn on background LED
        	digitalWrite(ob_LED, LOW);     // Turn off oddball LED
        	tone(tonepin, dataTemp[BGFREQ]);// Play background freq tone
        	digitalWrite(tone_copy, HIGH); // Turn on tone copy
			protocolState = STATE_CS;
			lastTone = isToneOn;
		}
		if (!isToneOn && (isToneOn != lastTone)) {
      		noTone(tonepin);                // Stop the tone
      		digitalWrite(bg_LED, LOW);      // Turn off background LED
      		digitalWrite(ob_LED, LOW);      // Turn off oddball LED
      		digitalWrite(tone_copy, LOW);   // Turn off tone copy
			protocolState = STATE_POST;
			lastTone = isToneOn;
		}
	}
}

void TECProtocol( unsigned long dt, bool isTone, bool isProbe ) {
	switch (protocolState ) {
		case STATE_PRE:
			if (dt > dataTemp[INITDELAY]) {
				protocolState = STATE_CS;
				nextt = dataTemp[INITDELAY] + dataTemp[TONEDUR];
				if ( isTone ) {
        			tone(tonepin, dataTemp[BGFREQ]);// Play background freq tone
      				digitalWrite(tone_copy, HIGH);   // Turn on tone copy
				} else {
      				digitalWrite(bg_LED, HIGH);   // Turn on light stim LED
				}
			}
			break;
		case STATE_CS:
			if (dt > nextt ) {
				protocolState = STATE_TRACE;
				nextt += dataTemp[ISI];
				if ( isTone ) {
      				noTone(tonepin);               	// End the tone
      				digitalWrite(tone_copy, LOW);   // Turn off tone copy
				} else {
      				digitalWrite(bg_LED, LOW);   // Turn off light stim LED
				}
			}
			break;
		case STATE_TRACE:
			if (dt > nextt ) {
				protocolState = STATE_US;
				nextt += dataTemp[PUFFDUR];
				if ( !isProbe )
      				digitalWrite(puffpin, HIGH);	// Turn on airpuff
			}
			break;
		case STATE_US:
			if (dt > nextt ) {
				protocolState = STATE_POST;
				nextt = dataTemp[TDUR];			// Trial duration
				if ( !isProbe )
      				digitalWrite(puffpin, LOW);   	// Turn off airpuff
			}
			break;
		case STATE_POST:
			if (dt > nextt ) {
				nextt = 0;						// Trial duration
			}
			break;
	}
}

void multiTraceProtocol( unsigned long dt ) {
}

// Possibly need interleave protocol too.

boolean doTrial( unsigned long startTime ) {
	/// Controls global actions like recording and trial end, and for
	/// the rest of it farms out the work to the individual protocols.
	unsigned long dt = millis() - startTime;
	if ( dataTemp[RECORDDUR]>0 ) {
		// Start and stop the trigger for camera and scope.
		if ( dt >= dataTemp[RECORDSTART] ) {
			digitalWrite( camera_pin, HIGH );
			digitalWrite( scope_pin, HIGH );
		}
		if ( dt >= dataTemp[RECORDSTART] + dataTemp[RECORDDUR] ) {
			digitalWrite( camera_pin, LOW );
			digitalWrite( scope_pin, LOW );
		}
	}
	switch (dataTemp[PROTOCOL]) {
		case PROTOCOL_GAP:
			gapProtocol( dt );
			break;
		case PROTOCOL_LIGHTTRACE:
			TECProtocol( dt, false, false ); // dt, isTone, isProbe
			break;
		case PROTOCOL_LIGHTPROBE:
			TECProtocol( dt, false, true  ); // dt, isTone, isProbe
			break;
		case PROTOCOL_SOUNDTRACE:
			TECProtocol( dt, true, false  ); // dt, isTone, isProbe
			break;
		case PROTOCOL_SOUNDPROBE:
			TECProtocol( dt, true, true  ); // dt, isTone, isProbe
			break;
		case PROTOCOL_MULTITRACE:
			multiTraceProtocol( dt );
			break;
		case PROTOCOL_MULTISOUND:
			multiTraceProtocol( dt );
			break;
		case PROTOCOL_MULTILIGHT:
			multiTraceProtocol( dt );
			break;
		default:
			break;
	}
	if ( dt > dataTemp[TDUR] ) {
		protocolState = STATE_PRE;
		return false;	// Used later for isTrail flag
	}
	return true;	// Used later for isTrail flag
}


/////////////////////////////////////////////////////////////////////
void setup() {
	dataTemp[RUNCONTROL] = 0;	// STOP: 0. START: 1. CONTINUE: 2. RESET: 3
	dataTemp[PROTOCOL] = 1; 	// GAP=0, SOUND: 1, LIGHT: 2, MULTI: 3
	dataTemp[RECORDSTART] = 500;// Time to start recording
	dataTemp[RECORDDUR] = 1000; // Duration of recording.
	dataTemp[TDUR] = 100;		// Trial duration (ms)
	dataTemp[INITDELAY] = 1000; // Initial delay before stimulus (ms)
	dataTemp[BGFREQ] = 5000;    // Background frequency (Hz)
	dataTemp[OBFREQ] = 1000;    // Oddball frequency (Hz)
	dataTemp[BGDUR] = 50; 		// Background tone duration (ms) OR:SOUNDDUR
	dataTemp[OBDUR] = 50; 		// Oddball tone duration (ms)  OR: LIGHTDUR
	dataTemp[OBPOS] = 6; 		// Oddball position
	dataTemp[PUFFDUR] = 10; 	// Air puff duration (ms)
	dataTemp[ISI] = 250; 		// Inter-stimulus interval (ms) OR: TRACEDUR
	dataTemp[ITI] = 1000; 		// Inter-trial interval (ms)
	dataTemp[TONENUMS] = 10; 	// Number of tones to play
	dataTemp[UPDATEINTERVAL] = 2; 	// Interval to update pin states
	// Initialize pins for input and output
	for (int i = 0; i < sizeof(digitalInputs) / sizeof(digitalInputs[0]); i++) {
		pinMode(digitalInputs[i], INPUT);
	}
	for (int i = 0; i < sizeof(digitalOutputs) / sizeof(digitalOutputs[0]); i++) {
		pinMode(digitalOutputs[i], OUTPUT);
	}
	pinMode(LED_BUILTIN, OUTPUT);
	Serial.begin(BAUDRATE);
}

void loop() {
	static unsigned long trialStartTime = 0;
	static unsigned long nextUpdateTime = 0;
	uint16_t receivedShorts[3] = {0,0,0};
	unsigned long currTime = millis();
	if ( currTime > nextUpdateTime )  {
		nextUpdateTime = currTime + dataTemp[UPDATEINTERVAL];
		if ( isTrial ) {
			isTrial = doTrial( trialStartTime );
  			sendToHost( (unsigned short)( millis() - currTime ) );
		}
		if ( recvFromHost( receivedShorts ) ) {
			if ( receivedShorts[1] < nParams ) {
				dataTemp[receivedShorts[1]] = receivedShorts[2];
			}
			if (receivedShorts[1] == RUNCONTROL) {
				if (dataTemp[RUNCONTROL] == START) {
					isTrial = true;
					nextt = 0;
					protocolState = STATE_PRE;
					trialStartTime = millis();
				} else if (dataTemp[RUNCONTROL] == STOP) {
			 		isTrial = false;
					protocolState = STATE_PRE;
				} else if (dataTemp[RUNCONTROL] == RESET) {
					isTrial = false;
					killAllActiveDigitalLines();
					protocolState = STATE_PRE;
				}
			}
		}
	}
}
