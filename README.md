# behaveArd: Project for arduino to control behaviour protocols

Copyright (C) 2021 Upinder S. Bhalla, National Centre for Biological Sciences,
Tata Institute of Fundamental Research, Bangalore, India.

All code in HOSS is licensed under GPL 3.0 or later.


## About
We use an Arduino to provide precise and reproducible timing for behavioural
experiments, and a matching Python program to harvest its timestamp data and 
to send the Arduino instructions about what to do next. This project includes
both the Arduino driver code, and the python interface to it. The Python 
interface displays the state of the behavioural protocol, i.e, the various
I/O lines of the Arduino, using ncurses.
