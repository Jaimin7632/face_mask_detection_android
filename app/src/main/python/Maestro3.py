#Maestro3.py

import colors
import constants
import isdate
import isnumber
import debug
import logging
import settings
#import Melexis 
import serial

import errno
import io
import socket
import sys
import os
import time
import glob
import datetime
import platform
import configparser
import psutil
import string
import random
import tkinter as tk
from tkinter import ttk
from queue import Queue
from inspect import getsourcefile
from os.path import abspath
from threading import Timer
from threading import Thread

logging.basicConfig(level=logging.DEBUG,
					format='%(relativeCreated)6d %(threadName)s %(message)s',
					)

doingScan = constants.notScanning

secondCnt = 0		
scanning = False
socketOpen = False
queueIRdata = False
StartScan = "Start Scan"
scanningTime = 0.0
blinkLed1 = 0
ErrorLabelTag = ""
strData = ""
InvalidAmbient = False			#07apr20 TJR
minNonScanTemp = 999.0			#21mar19 TJR
countMinScanTemps = 0			#21mar19 TJR
ScannerIR = -999.0
ScannerIRraw = -999.0			#07apr20 TJR
ScannerPointCount = 0
ScannerLastIndex = 0
SkippedPointCount = 0
ScannerPointValue = []
ResetLastIndex = False
DataPoint = 0.0
peakOut = -999.0
peakIRraw = -999.0
lastB1 = "*"
Qusers = None
IRdata = None
getIR = None
watcher = None
myName = ""
IRdataErrFlag=False
Wcfg = None						#17dec19 TJR
haveWelloCfg = False			#17dec19 TJR
axillary = False				#17dec19 TJR
avgAmbientPoints = 0			#08may20 TJR
avgAmbientTotal = 0				#08may20 TJR
cmdData = None					#27oct20 TJR
respData = None					#27oct20 TJR
serData = None					#27oct20 TJR
ser = None						#27oct20 TJR

def subprocess_call(*args, **kwargs):
	#also works for Popen. It creates a new *hidden* window, so it will work in frozen apps (.exe).
	if IS_WIN32:
		startupinfo = subprocess.STARTUPINFO()
		startupinfo.dwFlags = subprocess.CREATE_NEW_CONSOLE | subprocess.STARTF_USESHOWWINDOW
		startupinfo.wShowWindow = subprocess.SW_HIDE
		kwargs['startupinfo'] = startupinfo
	retcode = subprocess.call(*args, **kwargs)
	return retcode
				
def SecondTick():
	global secondCnt
	global Qusers
	global blinkLed1
	global msg

	secondCnt = secondCnt + 1
	if (blinkLed1 == 1):
		blinkLed1 = 2
	else:
		if (blinkLed1 == 2):
			blinkLed1 = 3
		else:
			if (blinkLed1 == 3):
				blinkLed1 = 0
				msg = "End Reception Blink"
				Qusers.put((3,msg))

	#logging.debug("Seconds: "+str(secondCnt))

	if (settings.showGUI == False):
		mainTick()

class SecondTimer(object):
	def __init__(self, interval, function, *args, **kwargs):
		self._timer     = None
		self.interval   = interval
		self.function   = function
		self.args       = args
		self.kwargs     = kwargs
		self.is_stopped = False
		self.is_running = False
		logging.debug("SecondTimer Init")
		self.start()
		
	def _run(self):
		
		logging.debug("SecondTimer Run")
		
		if (self.is_stopped == False):
			while (self.is_running == True):
				self.function()   #(*self.args, **self.kwargs)
				time.sleep(0.9)
				
	def start(self):
	
		logging.debug("SecondTimer Start")
		
		self._timer = Timer(self.interval, self._run)
		self._timer.start()
		self._timer.name = "sTimer"
		self.is_running = True

	def stop(self):
	
		logging.debug("SecondTimer Stop")
		
		self._timer.cancel()
		self.is_stopped = True
		self.is_running = False
		
def doprint(msg):								#22feb19 TJR
	if (settings.consoleOutput == True):		#22feb19 TJR		
		print(msg)								#22feb19 TJR
	else:										#22feb19 TJR
		logging.debug(msg)						#22feb19 TJR

def getIRpoint():									#09apr20 TJR
        global ScannerIRraw								#09apr20 TJR
        
        #logging.debug("getIRpoint doingScan: "+str(doingScan))
        dataS = ""
        eol = -1
        posT = -1
        if (settings.serialOpen == True):								#27oct20 TJR	
                dataS = doComm("C",False)      							#27oct20 TJR
                posT = dataS.find('T,')									#27oct20 TJR
                eol = dataS.find('\n') 									#27oct20 TJR
                ScannerIRraw = float(dataS[posT+2:eol])					#27oct20 TJR
        else:
                i = 0											#09apr20 TJR			
                ScannerIRraw = Melexis.Melexis(True)			#09apr20 TJR
                while (ScannerIRraw <= -99.0):					#09apr20 TJR
                        i += 1										#09apr20 TJR
                        if (i > 10):								#09apr20 TJR
                                ScannerIRraw = -999.0					#10apr20 TJR
                                break									#09apr20 TJR
                        else:										#09apr20 TJR
                                time.sleep(0.05)						#09apr20 TJR
                                ScannerIRraw = Melexis.Melexis(True)	#09apr20 TJR

def msTick():
	global SkippedPointCount
	global ScannerPointCount
	global ScannerLastIndex
	global ResetLastIndex
	global ScannerPointValue
	global ScannerIR
	global ScannerIRraw
	global scanning
	global queueIRdata
	global Qusers
	
	logMsg = ""
	scanning = True
	t = 0.0
	getIRpoint()
	if (ScannerIRraw == -999.0):
		settings.AbortScan = True
		logMsg = "No Data from IR Scanner"
		Qusers.put((1,logMsg))
		if (settings.showGUI == True):
			Error_var.set(logMsg)
		time.sleep(0.1)
	else:
		ScannerIR = round(ScannerIRraw, 1)
		t = round(time.time(),3)
		if (ResetLastIndex == True):
			ResetLastIndex = False
			ScannerPointCount = 0
			SkippedPointCount = 0
			ScannerLastIndex = 0

		if (queueIRdata == True):
			ScannerPointValue.append(ScannerIR)
			logMsg = "--Scanner#: "+str(ScannerPointCount)+" New = %0.1f" % ScannerIR
			ScannerPointCount = ScannerPointCount + 1
		else:
			SkippedPointCount = SkippedPointCount + 1
			if (settings.DebugNow == True):
				logMsg = "--Skipped#: "+str(SkippedPointCount)+" New = %0.1f" % ScannerIR

			if (ScannerPointCount == 0):
				ScannerPointValue.append(ScannerIR)
				ScannerPointCount = 1
				ScannerLastIndex = 0
			else:
				ScannerPointValue[ScannerLastIndex] = ScannerIR
		
	#logging.debug("< msTick "+logMsg)
	scanning = False

def serialData(serDat,cmds,resp):
	global debug

	logging.debug("Starting serialData")
	cmdIn = ""
	cmdS = ""
	responseB = b''
	bufferB = b''	
	waitingBytes = 0
	
	while (settings.serverRunning == True):
		if (cmds.empty() == True):
			time.sleep(0.01)   
		else:
			sent = 0
			respCnt = 1
			cmdIn = cmds.get()
			if (cmdIn[0].upper() == "M"):
				respCnt = 5

			cmdS = cmdIn + '\n'  #'\x0A\x0D' 					#add EOL
			#clear response queue
			while (resp.empty() == False):
				responseB = resp.get()

			sent = 0
			sent = serDat.write(cmdS.encode('utf-8')) 

			if (sent > 0):
				logging.debug("sent: "+cmdIn+" "+str(sent)+" bytes")
				bufferB = b''
				while (respCnt > 0):
					try:
						waitingBytes = serDat.inWaiting()
						responseB = serDat.read(1)
					except OSError as e:
						logging.debug("OS Err("+str(e)+") respCnt: "+str(respCnt))
						pass
					except serial.SerialException as e:
						logging.debug("Serial Err("+str(e)+") respCnt: "+str(respCnt))
						pass
					except serial.SerialTimeoutException:
						logging.debug("Serial TO Err - respCnt: "+str(respCnt))
						pass
					else:
						if (responseB == b''):
							logging.debug("Read - No Data - respCnt: "+str(respCnt))
							time.sleep(0.5)
						else:
							bufferB += responseB
							if (responseB == b'\n'):
								respCnt -= 1
								if (respCnt == 4):
									logging.debug("Response ("+str(respCnt)+"): "+str(bufferB))
									resp.put(bufferB)
									bufferB = b''
									time.sleep(1)

							if (respCnt == 0):
								logging.debug("Response(0): "+str(bufferB))
								resp.put(bufferB)
								bufferB = b''
					
	logging.debug("Exiting serialData")

def doComm(cmd,eightBit):
	global cmdData											#27oct20 TJR
	global respData											#27oct20 TJR

	dataS = ''
	dataB = b''
	if (cmd != ''):											#03nov20 TJR
		cmdData.put(cmd)									#27oct20 TJR
	while (respData.empty() == True):						#27oct20 TJR
		time.sleep(0.01)   									#27oct20 TJR
	
	if (eightBit == True):
		dataB = respData.get()      						#27oct20 TJR
		return dataB
	else:
		dataS = respData.get().decode('utf-8')				#27oct20 TJR
		return dataS
		
def getIRdata(Qu):
	global queueIRdata
	global scanning
	
	qVal = 0
	logging.debug("Starting getIRdata")
	
	while (settings.serverRunning == True):
		scanningSkips = 0
		
		while (scanning == True):
			scanningSkips = scanningSkips + 1
			time.sleep(0.01)
			
		if (scanningSkips != 0):
			if (settings.DebugNow == True):
				logging.debug("**Scanning Skips#: "+str(scanningSkips))
			
		if (Qu.empty() == True):
			time.sleep(0.01)   
		else:
			qVal = Qu.get()
			if (qVal == 1):
				queueIRdata = True
				while ((Qu.empty()) and (queueIRdata == True)):
					msTick()
					time.sleep(0.01)
				logging.debug("Exiting fast point acquisition w/queue")
			else:
				msTick()	
				
	logging.debug("Exiting getIRdata")
	
def doAbout2(event):
	doAbout()
	
def doAbout():
	
	if settings.showingAbout > 0:
		settings.showingAbout = settings.showingAbout - 1000
		AboutFrame.place(x=-400,y=settings.showingAbout)
	else:
		settings.showingAbout = settings.showingAbout + 1000
		AboutFrame.place(x=5,y=settings.showingAbout)
		
	AboutFrame.update()
	
def doExit():
	global sT0
	global msT0
	
	sT0.stop()
	time.sleep(1.1)

	if (settings.DebugNow == True):
		debug.LogAction("'Exit'",True)	
		
	if (settings.showGUI == True):		#05jul18 TJR
		root.destroy()
	else:
		settings.showGUI = True
			
def doXlate1():
	doXlate(1)
		
def doXlate(which):
	global myName

	section = myName
	if (settings.allowXlate == 2):
		settings.allowXlate = 0
	else:
		settings.allowXlate = 2

	settings.ini.set(section,"allowXlate",str(settings.allowXlate))
	updateIniFile()

def doLog():
	global myName

	section = myName
	if WriteLog_var.get() == 0:
		settings.LogCheck = 0
	else:
		settings.LogCheck = 1
	settings.ini.set(section,"LogCheck",str(settings.LogCheck))
	updateIniFile()

def serial_ports():
    """ Lists serial port names

        :raises EnvironmentError:
            On unsupported or unknown platforms
        :returns:
            A list of the serial ports available on the system
    """
    if sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Unsupported platform')

    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result

def doData():
	global myName

	section = myName
	if WriteData_var.get() == 0:
		settings.DataCheck = 0
	else:
		settings.DataCheck = 1
	settings.ini.set(section,"DataCheck",str(settings.DataCheck))
	updateIniFile()
							
def doStationaryDelay():
	global myName
	
	getNoStr = ""
	getNoVal = 0.0
#	getNoStr = StationaryDelay_var.get()
#
#	if isnumber.is_numeric(getNoStr):
#		getNoVal = float(getNoStr)
#		section = myName
#		settings.StationaryDelay = getNoVal
#		settings.ini.set(section,"StationaryDelay",getNoStr)
#		updateIniFile()
#		return True
#	else:
#		return False
	
def doStationaryScanTime():
	global myName
	
	getNoStr = ""
	getNoVal = 0.0
#	getNoStr = StationaryScanTime_var.get()
#
#	if isnumber.is_numeric(getNoStr):
#		getNoVal = float(getNoStr)
#		section = myName
#		settings.StationaryScanTime = getNoVal
#		settings.ini.set(section,"StationaryScanTime",getNoStr)
#		updateIniFile()
#		return True
#	else:
#		return False
	
def doPause():
	
	if (settings.paused == False):
		if (settings.showGUI == True):
			PauseButton.configure(text="Resume")
			WaitingLabel.configure(bg=constants.Back_Color)
		settings.paused = True
		if (settings.DebugNow == True):
			debug.LogAction("'Paused'", True)
	else:
		if (settings.showGUI == True):
			PauseButton.configure(text="Pause")
			WaitingLabel.configure(bg=constants.Grey_Color)
		settings.paused = False
		if (settings.DebugNow == True):
			debug.LogAction("'Resumed'",True)
	
def addException(text):

	if (settings.showGUI == True):
		exceptionList.insert(tk.END, text)
	else:
		doprint("Exception: "+text)

	if (settings.DebugNow == True):
		debug.LogAction("Exception: "+text, True)
	
def addHistory(text):
	
	if (settings.showGUI == True):
		historyList.insert(tk.END, text)
	else:
		doprint("History: "+text)
			
def WriteDataFile():
	global DataPoint
	global ErrorLabelTag

	text = ""
	err = 0
	errMsg = ""
	DataBuffer = ""
	
	text = str(DataPoint)
	if len(settings.DataFile) > 0:
		try:
			out = open(settings.DataFile, 'w')
		except OSError as e:
			err = e.errno
			errMsg = e.strerror
			doprint("Err("+str(err)+") Opening Data File: "+settings.DataFile+" - "+errMsg)
		else:
			DataBuffer += "Max " + str(settings.OverAllMaxPtValue) + "\n"
			if (settings.ScanComplete == True):
				if (len(ErrorLabelTag) > 0):
					DataBuffer += "ERROR: "	+ ErrorLabelTag + "\n"
				else:
					if (settings.AbortScan == True):
						DataBuffer += "Aborted \n"
					else:
						DataBuffer += "Completed \n"
			else:
				DataBuffer += "Ok \n"

			try:
				out.write(DataBuffer)
			except OSError as e:
				err = e.errno
				errMsg = e.strerror
				doprint("Err("+str(err)+") Writing Data File: "+settings.DataFile+" - "+errMsg)
			else:
				out.close()

def sendResults(LastLine, sock=None, Q=None):
	global peakOut
	global peakIRraw
	global minNonScanTemp 	#08apr20 TJR
	global InvalidAmbient	#08apr20 TJR

	ST1 = b""
	EncodedData = "".encode(encoding='UTF-8') 


	ST1 = bytes(str(round(minNonScanTemp,1)),encoding='UTF-8')   					#21mar19 TJR
	if (InvalidAmbient == True):				#08apr20 TJR
		EncodedData = b"+M0,0,"+ST1+b"\n"		#08apr20 TJR
	else:										#08apr20 TJR
		EncodedData = b"+M0,0,"+ST1+b"\n"					

	if (sock != None):
		processRecord(EncodedData, sock, Q)
		time.sleep(0.05)
	else:
		logging.debug("fake send: "+str(EncodedData))

	ST1 = bytes(str(round(peakIRraw,1)),encoding='UTF-8')                                                                         
	EncodedData = b"+p0,0,"+ST1+b"\n"		
	if (sock != None):																 
		processRecord(EncodedData, sock, Q)
		time.sleep(0.05)
	else:
		logging.debug("fake send: "+str(EncodedData))

	ST1 = bytes(str(round(peakOut,1)),encoding='UTF-8')                                                                   
	EncodedData = b"+P0,0,"+ST1+b"\n"
	if (sock != None):																					 
		processRecord(EncodedData, sock, Q)
		time.sleep(0.05)
	else:
		logging.debug("fake send: "+str(EncodedData))

	if len(LastLine) > 0:
		EncodedData = LastLine
		if (sock != None):		
			processRecord(EncodedData, sock, Q)
			time.sleep(0.1)
		else:
			logging.debug("fake send: "+str(EncodedData))

def getHome():
	home = os.curdir                      

	if 'HOME' in os.environ:
		home = os.environ['HOME']
	elif os.name == 'posix':
		home = os.path.expanduser("~/")
	elif os.name == 'nt':
		if 'HOMEPATH' in os.environ and 'HOMEDRIVE' in os.environ:
			home = os.environ['HOMEDRIVE'] + os.environ['HOMEPATH']
	else:
		home = os.environ['HOMEPATH']
	return home

def getUser():
	user = ""
	name = ""

	for name in ('LOGNAME', 'USER', 'LNAME', 'USERNAME'):
		user = os.environ.get(name)
		if user:
			return user
 
	# If not user from os.environ.get()
	import pwd
	user = pwd.getpwuid(os.getuid())[0]
	return user
	
def updateIniFile():
	global myName
	
	err = 0
	errMsg = ""
	section = myName
	
	try:
		iniObj = open(settings.iniFileName,"w")
	except OSError as e:
		err = e.errno
		errMsg = e.strerror
		doprint('Error opening .ini File ('+settings.iniFileName+') err ('+str(err)+'): '+errMsg)
	else:
		settings.ini.write(iniObj)
		iniObj.close()

def updateAmbient(newValue,updateIni):
	global minNonScanTemp		#09apr20 TJR
	global InvalidAmbient		#09apr20 TJR
	global myName				#09apr20 TJR

	minNonScanTemp = newValue																		#09apr20 TJR
	scale = ""																						#13apr20 TJR
	invalid = ""
	if  ((minNonScanTemp < settings.MinAmbientScan) or (minNonScanTemp > settings.MaxAmbientScan)):	#08apr20 TJR
		InvalidAmbient = True																		#08apr20 TJR
		invalid = " > Invalid <"																	#09apr20 TJR
		if (settings.showGUI == True):																#09apr20 TJR
			AmbientX_var.set("%0.1f" % minNonScanTemp)												#09apr20 TJR
			AmbientXLabel.configure(bg=constants.PaleRed_Color)										#09apr20 TJR
	else: 																							#09apr20 TJR
		InvalidAmbient = False																		#09apr20 TJR
		if (settings.showGUI == True):																#09apr20 TJR
			AmbientX_var.set("%0.1f" % minNonScanTemp)												#09apr20 TJR
			AmbientXLabel.configure(bg=constants.PaleGreen_Color)									#09apr20 TJR

	logging.debug("Ambient Changed: " + str(round(minNonScanTemp,1)) + invalid)						#09apr20 TJR

	if updateIni:
		if (settings.OutputValueC == True):												#13apr20 TJR
			scale = "C"																	#13apr20 TJR
		elif (settings.OutputValueK == True):											#13apr20 TJR
			scale = "K"																	#13apr20 TJR
		else:																			#13apr20 TJR
			scale = "F"																	#13apr20 TJR
		section = myName												    	#09apr20 TJR	
		settings.ini.set(section,"ambient",str(round(minNonScanTemp,1))+scale)	#09apr20 TJR
		updateIniFile()													    	#09apr20 TJR	

def readConfig():
	global Wcfg
	global haveWelloCfg
	global axillary
	global myName

	buffer = ""
	settings.allowXlate = 2
	settings.DataCheck = 0
	settings.LogCheck = 0
	settings.Stationary = True
	settings.StationaryDelay = 0.045
	settings.StationaryScanTime = 3
	settings.ShowBadScanData = True
	settings.GetTempDuringMove = False
	settings.TCPIPinAddr = ""	#127.0.0.1
	settings.TCPIPinPort = 6789
	settings.TCPIPdataSize = 4096
	settings.serialPort = ""
	settings.serialBaud = 115200
	settings.serialParity = "N"
	settings.serialBits = 8
	settings.serialStopBits = 1
	settings.serialStartDelay = 3
	settings.serialOpen = False
	settings.xLF1 = 1
	settings.xLF2 = 2
	settings.MinAmbientScan = 50
	settings.MaxAmbientScan = 90
	settings.OutputValueF = True
	settings.OutputValueC = False
	settings.OutputValueK = False
	settings.ActualOutsideXlate = True	#30mar20 TJR
	settings.WelloCfg = ""				#17dec19 TJR
	settings.WelloSection = ""			#17dec19 TJR
	settings.WelloKey = ""				#17dec19 TJR
	settings.UseAvg = True              #16nov20 TJR

	err = 0
	i = 0
	j = 0
	k = [-1,0,0,0,0,0,0,0]
	fe = 0
	f1 = ""
	f2 = ""
	x = 0
	v = 0.0
	last = ""
	errMsg = ""
	section = ""
	message = ""
	key = ""
	fullName = ""
	strValue = ""
	words = []
	addHistory(".cfg = "+settings.configFileName)
	if (settings.haveIni == False):
		addHistory("No .ini File ('+settings.iniFileName+') found.")

	if (settings.haveConfig == True):
		section = myName
		settings.Ver = settings.getCfgString(settings.config,section,'Ver',False,False)
		settings.Header = settings.getCfgString(settings.config,section,'Header',False,False)
		settings.What = settings.getCfgString(settings.config,section,'What',False,False) 
		strValue = settings.getCfgString(settings.config,section,'RunCount',True,False)
		if len(strValue) > 0:
			settings.RunCount = int(strValue)         
		strValue = settings.getCfgString(settings.config,section,'LogFile',False,False)
		if len(strValue) > 0:
			settings.LogFile = settings.MakeSureOfPath(strValue)	
			if len(settings.LogFile) > 0:
				debug.LogAction("Restarted.", True)
				addHistory( "Logging to: "+settings.LogFile)
		strValue = settings.getCfgString(settings.config,section,'DataFile',False,False)
		if len(strValue) > 0:
			settings.DataFile = settings.MakeSureOfPath(strValue)	
			if len(settings.DataFile) > 0:
				addHistory( "Data File: "+settings.DataFile)
		strValue = settings.getCfgString(settings.config,section,'xLateSkinTempFile',False,False)
		if len(strValue) > 0:
			settings.xLateSkinTempFile = settings.MakeSureOfPath(strValue)	
			if len(settings.xLateSkinTempFile) > 0:
				addHistory( "xLate File: "+settings.xLateSkinTempFile)
		strValue = settings.getCfgString(settings.config,section,'xLateSkinAxTempFile',False,False)		#17dec19 TJR
		if len(strValue) > 0:																			#17dec19 TJR
			settings.xLateSkinAxTempFile = settings.MakeSureOfPath(strValue)							#17dec19 TJR
			if len(settings.xLateSkinAxTempFile) > 0:													#17dec19 TJR
				addHistory( "AxXlate File: "+settings.xLateSkinAxTempFile)								#17dec19 TJR
		strValue = settings.getCfgString(settings.config,section,'MaxList',True,False)
		if len(strValue) > 0:
			settings.MaxList = int(strValue)
		strValue = settings.getCfgString(settings.config,section,'ShowBadScanData',False,False)
		if strValue.upper() == "FALSE":
			settings.ShowBadScanData = False
		strValue = settings.getCfgString(settings.config,section,'StationaryScanTime',True,False)
		if len(strValue) > 0:
			settings.StationaryScanTime = float(strValue)
		strValue = settings.getCfgString(settings.config,section,'StationaryDelay',True,False)
		if len(strValue) > 0:
			settings.StationaryDelay = float(strValue)
		strValue = settings.getCfgString(settings.config,section,'GetTempDuringMove',False,False)
		if strValue.upper() == "TRUE":
			settings.GetTempDuringMove = True      
		strValue = settings.getCfgString(settings.config,section,'ActualOutsideXlate',False,False)			#30mar20 TJR
		if strValue.upper() == "TRUE":																		#30mar20 TJR
			settings.ActualOutsideXlate = True
			logging.debug( "ActualOutsideXlate: True")				#20oct20 TJR
		else:																								#30mar20 TJR
			settings.ActualOutsideXlate = False   	
			logging.debug( "ActualOutsideXlate: False")				#20oct20 TJR	
		strValue = settings.getCfgString(settings.config,section,'UseAvg',False,False)						#16nov20 TJR
		if strValue.upper() == "TRUE":																		#16nov20 TJR
			settings.UseAvg = True
			logging.debug( "UseAvg: True")																	#16nov20 TJR
		else:																								#16nov20 TJR
			settings.UseAvg = False   	
			logging.debug( "UseAvg: False")																	#16nov20 TJR	

		strValue = settings.getCfgString(settings.config,section,'xLF1',True,False)							#04nov20 TJR
		if len(strValue) > 0:																				#04nov20 TJR
			settings.xLF1 = int(strValue)      																#04nov20 TJR
		strValue = settings.getCfgString(settings.config,section,'xLF2',True,False)							#04nov20 TJR
		if len(strValue) > 0:																				#04nov20 TJR
			settings.xLF2 = int(strValue)  																	#04nov20 TJR
			
		settings.TCPIPinAddr = settings.getCfgString(settings.config,section,'TCPIPinAddr',False,False)	
		if (len(settings.TCPIPinAddr) == 0):
			settings.TCPIPinAddr = settings.localIP
		strValue = settings.getCfgString(settings.config,section,'TCPIPinPort',True,False)
		if len(strValue) > 0:
			settings.TCPIPinPort = int(strValue)
		strValue = settings.getCfgString(settings.config,section,'TCPIPdataSize',True,False)
		if len(strValue) > 0:
			settings.TCPIPdataSize = int(strValue)

		strValue = settings.getCfgString(settings.config,section,'serialPort',False,False)
		if len(strValue) > 0:
			settings.serialPort = strValue
		strValue = settings.getCfgString(settings.config,section,'serialBaud',True,False)
		if len(strValue) > 0:
			settings.serialBaud = int(strValue)
		strValue = settings.getCfgString(settings.config,section,'serialParity',False,False)
		if len(strValue) > 0:
			settings.serialParity = strValue
		strValue = settings.getCfgString(settings.config,section,'serialBits',True,False)
		if len(strValue) > 0:
			settings.serialBits = int(strValue)
		strValue = settings.getCfgString(settings.config,section,'serialStopBits',True,False)
		if len(strValue) > 0:
			settings.serialStopBits = int(strValue)
		strValue = settings.getCfgString(settings.config,section,'serialStartDelay',True,False)
		if len(strValue) > 0:
			settings.serialStartDelay = int(strValue)

		strValue = settings.getCfgString(settings.config,section,'OutputValue',False,False)
		if len(strValue) > 0:
			if (strValue == 'F'):
				settings.OutputValueF = True
				settings.OutputValueC = False
				settings.OutputValueK = False
			elif (strValue == 'C'):
				settings.OutputValueF = False
				settings.OutputValueC = True
				settings.OutputValueK = False
			elif (strValue == 'K'):
				settings.OutputValueF = False
				settings.OutputValueC = False
				settings.OutputValueK = True
		strValue = settings.getCfgString(settings.config,section,'MinAmbientScan',True,False)
		if len(strValue) > 0:
			settings.MinAmbientScan = float(strValue)
		strValue = settings.getCfgString(settings.config,section,'MaxAmbientScan',True,False)
		if len(strValue) > 0:
			settings.MaxAmbientScan = float(strValue)
		if (settings.OutputValueC == True):
			settings.MinAmbientScan = round(((settings.MinAmbientScan - 32) * 5) / 9,2)
			settings.MaxAmbientScan = round(((settings.MaxAmbientScan - 32) * 5) / 9,2)
		if (settings.OutputValueK == True):
			settings.MinAmbientScan = round(((settings.MinAmbientScan + 459.67) * 5) / 9,2)
			settings.MaxAmbientScan = round(((settings.MaxAmbientScan + 459.67) * 5) / 9,2)		
						
		i = 0
		strValue = settings.getCfgString(settings.config,section,'BackColor'+str(i),False,False)
		while (len(strValue) > 0):
			if strValue.find(",") != -1:
				words = strValue.split(",")
				settings.ColorsRange[i] = colors.Color3(int(words[0]),int(words[1]),int(words[2]))
			else:
				settings.ColorsRange[i] = colors.Color1(strValue)
			i = i + 1
			strValue = settings.getCfgString(settings.config,section,'BackColor'+str(i),False,False)
		i = 0
		strValue = settings.getCfgString(settings.config,section,'ForeColor'+str(i),False,False)
		while (len(strValue) > 0):
			if strValue.find(",") != -1:
				words = strValue.split(",")
				settings.ColorsRange2[i] = colors.Color3(int(words[0]),int(words[1]),int(words[2]))
			else:
				settings.ColorsRange2[i] = colors.Color1(strValue)
			i = i + 1
			strValue = settings.getCfgString(settings.config,section,'ForeColor'+str(i),False,False)

		strValue = settings.getCfgString(settings.config,section,'WelloCfg',False,False)				#17dec19 TJR
		if len(strValue) > 0:																			#17dec19 TJR
			settings.WelloCfg = settings.MakeSureOfPath(strValue)										#17dec19 TJR
		if (len(settings.WelloCfg) > 0):																#17dec19 TJR
			strValue = settings.getCfgString(settings.config,section,'WelloSection',False,False)		#17dec19 TJR
			if len(strValue) > 0:																		#17dec19 TJR
				settings.WelloSection = strValue														#17dec19 TJR
				if (len(settings.WelloSection) > 0):													#17dec19 TJR
					strValue = settings.getCfgString(settings.config,section,'WelloKey',False,False)	#17dec19 TJR
					if len(strValue) > 0:																#17dec19 TJR
						settings.WelloKey = strValue													#17dec19 TJR
			
		section = myName    
		if (settings.haveIni == True):
			strValue = settings.getCfgString(settings.ini,section,'allowXlate',True,False)
			if (len(strValue) > 0):
				settings.allowXlate = int(strValue)
			strValue = settings.getCfgString(settings.ini,section,'DataCheck',True,False)
			if (len(strValue) > 0):
				settings.DataCheck = int(strValue)
			strValue = settings.getCfgString(settings.ini,section,'LogCheck',True,False)
			if (len(strValue) > 0):
				settings.LogCheck = int(strValue)
			strValue = settings.getCfgString(settings.ini,section,'ambient',False,False)						#09apr20 TJR
			if (len(strValue) > 0):																				#09apr20 TJR
				last = strValue[len(strValue)-1:]					#13apr20 TJR
				if (last == "F"):									#13apr20 TJR
					v = float(strValue[0:len(strValue)-1])			#13apr20 TJR
					if (settings.OutputValueF == True):				#13apr20 TJR
						updateAmbient(v,False)						#13apr20 TJR
					elif (settings.OutputValueC == True):			#13apr20 TJR
						v = ((v-32)*5)/9							#13apr20 TJR
						updateAmbient(v,False)						#13apr20 TJR
					else:											#13apr20 TJR
						v = round(((v + 459.67) * 5) / 9,2)			#13apr20 TJR
						updateAmbient(v,False)						#13apr20 TJR
				elif (last == "C"):									#13apr20 TJR
					v = float(strValue[0:len(strValue)-1])			#13apr20 TJR
					if (settings.OutputValueC == True):				#13apr20 TJR
						updateAmbient(v,False)						#13apr20 TJR
					else:											#13apr20 TJR
						v = ((9*v)/5)+32							#13apr20 TJR
						if (settings.OutputValueF == True):			#13apr20 TJR
							updateAmbient(v,False)					#13apr20 TJR
						else:										#13apr20 TJR
							v = round(((v + 459.67) * 5) / 9,2)		#13apr20 TJR
							updateAmbient(v,False)					#13apr20 TJR
				elif (last == "K"):									#13apr20 TJR
					v = float(strValue[0:len(strValue)-1])			#13apr20 TJR
					if (settings.OutputValueK == True):				#13apr20 TJR
						updateAmbient(v,False)						#13apr20 TJR
					else:											#13apr20 TJR
						v = v - 273.15								#13apr20 TJR
						if (settings.OutputValueC == True):			#13apr20 TJR
							updateAmbient(v,False)					#13apr20 TJR
						else:										#13apr20 TJR
							v = ((v * 9.0) / 5.0) + 32.0			#13apr20 TJR
							updateAmbient(v,False)					#13apr20 TJR
				else:												#13apr20 TJR
					v = float(strValue)								#13apr20 TJR
					if (settings.OutputValueF == True):				#13apr20 TJR
						updateAmbient(v,False)						#13apr20 TJR
					elif (settings.OutputValueC == True):			#13apr20 TJR
						v = ((v-32)*5)/9							#13apr20 TJR
						updateAmbient(v,False)						#13apr20 TJR
					else:											#13apr20 TJR
						v = round(((v + 459.67) * 5) / 9,2)			#13apr20 TJR
						updateAmbient(v,False)						#13apr20 TJR
	
#			strValue = settings.getCfgString(settings.ini,section,'StationaryDelay',True,False)
#			if (len(strValue) > 0):
#				settings.StationaryDelay = float(strValue)
#			strValue = settings.getCfgString(settings.ini,section,'StationaryScanTime',True,False)
#			if (len(strValue) > 0):
#				settings.StationaryScanTime = float(strValue)	

		else:
			try:
				iniObj = open(settings.iniFileName,"w")
			except OSError as e:
				err = e.errno
				errMsg = e.strerror
				doprint('Error opening .ini File ('+settings.iniFileName+') err ('+str(err)+'): '+errMsg)
			else:
				
				settings.ini.add_section(section)
				settings.ini.set(section,"allowXlate",str(settings.allowXlate))
				settings.ini.set(section,"DataCheck",str(settings.DataCheck))
				settings.ini.set(section,"LogCheck",str(settings.LogCheck))
				settings.ini.set(section,"StationaryDelay",str(settings.StationaryDelay))
#				settings.ini.set(section,"StationaryScanTime",str(settings.StationaryScanTime))
#				settings.ini.write(iniObj)
				iniObj.close()

		#doprint("wello.cfg = "+settings.WelloCfg)			#17dec19 TJR

		if len(settings.WelloCfg) > 0:
			logging.debug("wello.cfg = "+settings.WelloCfg)		#17dec19 TJR
			err = 0												#17dec19 TJR
			errMsg = ""											#17dec19 TJR
			Wcfg = configparser.ConfigParser(allow_no_value=True,comment_prefixes=('.'),empty_lines_in_values=False)
			Wcfg.sections()										#17dec19 TJR
			try:												#17dec19 TJR
				Wcfg.read(settings.WelloCfg)					#17dec19 TJR
			except OSError as e:								#17dec19 TJR
				err = e.errno									#17dec19 TJR
				errMsg = e.strerror								#17dec19 TJR
			else:												#17dec19 TJR
				haveWelloCfg = True								#17dec19 TJR
				strValue = settings.getCfgString(Wcfg,settings.WelloSection,settings.WelloKey,False,False)	#17dec19 TJR
				if (len(strValue) > 0):							#17dec19 TJR
					if (strValue.upper() == "TRUE"):			#17dec19 TJR
						axillary = True							#17dec19 TJR
					else:										#17dec19 TJR
						axillary = False						#17dec19 TJR

		i = 0																		#17dec19 TJR
		settings.xLateTempsCount = 0										
		if axillary == True:														#17dec19 TJR
			if len(settings.xLateSkinAxTempFile) > 0:								#17dec19 TJR
				i = 1																#17dec19 TJR
				logging.debug("xLate From: "+settings.xLateSkinAxTempFile)			#17dec19 TJR
		else:																		#17dec19 TJR
			if len(settings.xLateSkinTempFile) > 0:									#17dec19 TJR
				i = 1																#17dec19 TJR
				logging.debug("xLate From: "+settings.xLateSkinTempFile)			#17dec19 TJR

		if i > 0:																	#17dec19 TJR
			err = 0
			errMsg = ""
			try:
				if axillary == True:												#17dec19 TJR
					buffer = open(settings.xLateSkinAxTempFile, 'r').read()			#17dec19 TJR
				else:																#17dec19 TJR
					buffer = open(settings.xLateSkinTempFile, 'r').read()
			except OSError as e:
				err = e.errno
				errMsg = e.strerror
			else:
				j = 0
				i = buffer.find("\n",j)
				fe = i														#04nov20 TJR
				while (i > 0): 
					line = buffer[j:i]
					print(line)
					if (line[0] != "."):									#04nov20 TJR
						x = 1												#04nov20 TJR
						while (x > 0):										#04nov20 TJR
							k[x] = line.find(",",k[x-1]+1)					#04nov20 TJR
							if (k[x] > 0):									#04nov20 TJR
								k[x+1] = line.find(",",k[x]+1)				#04nov20 TJR
								x += 1										#04nov20 TJR
							else:											#04nov20 TJR
								k[x] = fe									#04nov20 TJR
								break										#04nov20 TJR

						if (k[settings.xLF1] >= 0) and (k[settings.xLF2] >= 0):
							f1 = line[k[settings.xLF1-1]+1:k[settings.xLF1]]
							if isnumber.is_numeric(f1):
								f2 = line[k[settings.xLF2-1]+1:k[settings.xLF2]]
								if isnumber.is_numeric(f2):
									if (settings.OutputValueC == True):												#13apr20 TJR
										settings.TempIn.append(round(((float(f1) - 32) * 5) / 9,2))					#13apr20 TJR
										settings.TempOut.append(round(((float(f2) - 32) * 5) / 9,2))				#13apr20 TJR
									elif (settings.OutputValueK == True):											#13apr20 TJR
										settings.TempIn.append(round(((float(f1) + 459.67) * 5) / 9,2))				#13apr20 TJR
										settings.TempIn.append(round(((float(f2) + 459.67) * 5) / 9,2))				#13apr20 TJR
									else:																			#13apr20 TJR			
										settings.TempIn.append(float(f1))
										settings.TempOut.append(float(f2))

									settings.xLateTempsCount = settings.xLateTempsCount + 1
									j = i+len("\n")
									i = buffer.find("\n",j)
									line = ""
								else:
									i = -999
							else:
								i = -999
						else:
							i = -999
					else:																							#04nov20 tjr
						j = i+len("\n")																				#04nov20 tjr
						i = buffer.find("\n",j)																		#04nov20 tjr
						line = ""																					#04nov20 tjr
		else:
			if axillary == True:												#17dec19 TJR
				logging.debug("xLateSkinAxTempFile Not Defined")				#17dec19 TJR
			else:																#17dec19 TJR
				logging.debug("xLateSkinTempFile Not Defined")

		if i == -999:
			if axillary == True:												#17dec19 TJR
				logging.debug("Format error processing xLateSkinAxTempFile: "+settings.xLateSkinAxTempFile)
			else:
				logging.debug("Format error processing xLateSkinTempFile: "+settings.xLateSkinTempFile)
		else:
			if axillary == True:												#17dec19 TJR
				logging.debug("Xlat file: "+settings.xLateSkinAxTempFile+" contains: "+str(settings.xLateTempsCount)+" points")
			else:
				logging.debug("Xlat file: "+settings.xLateSkinTempFile+" contains: "+str(settings.xLateTempsCount)+" points")
			
	return err

def processRecord(data, sock, Q):	
	global socketOpen
	global doingScan

	err = 0
	errMsg = ""
	Msg = ""
	LineOut1 = ""

	if ((sock != None) and (socketOpen == True)):
		LineOut1 = ">> processRecord send: " + str(data)
		doprint(LineOut1)
		debug.LogAction(LineOut1, True)
		logging.debug(LineOut1) 

		Q.put((0,"Record: "+str(data)))
		try:
			sock.send(data)
		except OSError as e:
			err = e.errno
			errMsg = e.strerror
			Msg = "Socket Send Error (" + str(err) + "): " + errMsg
			debug.LogAction(Msg, True)
			logging.debug(Msg)
			if (err == 32):															#15mar17 TJR
				Msg = "Socket Closed"												#15mar17 TJR
				Q.put((-1,Msg))														#15mar17 TJR
				sock.close()														#15mar17 TJR
				socketOpen = False													#15mar17 TJR
				Msg = "SocketOpen State: False (processRecord)"						#16mar17 TJR
				debug.LogAction(Msg, True)											#16mar17 TJR
				logging.debug(Msg)													#16mar17 TJR
				if (doingScan != constants.notScanning):			#24apr20 TJR
					doingScan = constants.abortScanning				#24apr20 TJR
				settings.AbortScan = True 											#15mar17 TJR
				addException("Socket Send Error: Closing Socket, Aborting Scan")	#15mar17 TJR
	else:	
		if sock == None:
			LineOut1 = ">> processRecord (Sock=None) cant's send: " + str(data)
			doprint(LineOut1)
			debug.LogAction(LineOut1, True)
			logging.debug(LineOut1) 
		else:
			LineOut1 = ">> processRecord called with Socket Closed; cant's send: " + str(data)
			Msg = "Socket Closed"													#15mar17 TJR
			Q.put((-1,Msg))															#15mar17 TJR
			sock.close()															#15mar17 TJR
			doprint(LineOut1)
			debug.LogAction(LineOut1, True)
			logging.debug(LineOut1)
	
def ReadData(Buffer):
	i = 0
	fin = True
	rsv1 = True
	rsv2 = True
	rsv3 = True
	opCode = 0
	Payload = 0
	mask = True
	Length = 0
	maskKeys = ''.encode(encoding='UTF-8')   #bytes()
	Data = ''.encode(encoding='UTF-8')   #bytes()
	CloseCode = 0
	Packet = ""
	DataPos = 0

	fin = (Buffer[0] & 0x080) == 0x080
	rsv1 = (Buffer[0] & 0x040) == 0x040
	rsv2 = (Buffer[0] & 0x020) == 0x020
	rsv3 = (Buffer[0] & 0x010) == 0x010
	
	opCode = Buffer[0] & 0x00F
	mask = (Buffer[1] & 0x080) == 0x080

	Payload = Buffer[1] & 0x07F
	Length = 0
	
	if Payload == 126:
		Length = (Buffer[2] * 256) + Buffer[3]
		DataPos = 4
	elif Payload == 127:
		Length = (Buffer[2] * (256 * 256 * 256 * 256)) + (Buffer[3] * (256 * 256 * 256)) + (Buffer[4] * (256 * 256)) + (Buffer[5] * 256) + (Buffer[6] * 1)
		DataPos = 8
	else:
		Length = Payload
		DataPos = 2
	
	maskKeys[0] = 0
	maskKeys[1] = 0
	maskKeys[2] = 0
	maskKeys[4] = 0

	if (mask):
		i = 0
		while (i <= 3):
			maskKeys[i] = Buffer[DataPos + i]
			i = i + 1
		DataPos = DataPos + 4
	
	Data = []
	i = 0
	while (i <= Length - 1):
		if mask:
			Data.append(Buffer[DataPos + i] ^ maskKeys[i % 4])
		else:
			Data.append(Buffer[DataPos + i])

	CloseCode = 0
	if opCode == 8:
		if Length > 1:
			CloseCode = Data[0] + (Data[1] * 256)

	if Length >= 1:
		Packet = []
		if CloseCode != 0:
			i = 0
			while (i <= Length - 1):
				Packet.append(Chr(Data[i+2]))
				i = i + 1
		else:
			i = 0
			while (i <= Length - 1):
				Packet.append(Chr(Data[i]))
				i = i + 1
	else:
		Packet = ""

	return Packet
	
def GetNextTemp():
	global ScannerPointCount
	global SkippedPointCount
	global scanning
	global ScannerIR
	global IRdata
	global IRdataErrFlag
	global queueIRdata
	
	countWas = 0
	diff = 0
	skps = 0
	
	if (settings.DebugNow == True):
		if (scanning == True):
			logging.debug("Entered GetNextTemp Scanning: True")

	while (diff == 0):
		skps = 0
		if (queueIRdata == True):
			countWas = ScannerPointCount
			IRdata.put(1)

			while ((countWas == ScannerPointCount) and (skps < 20)):
				skps = skps + 1
				time.sleep(0.01)
		    
			IRdata.put(0)
			diff = ScannerPointCount - countWas
			if (settings.showGUI == True):
				Count1_var.set(str(ScannerPointCount))
		else:
			countWas = SkippedPointCount
			IRdata.put(0)

			while ((countWas == SkippedPointCount) and (skps < 20)):
				skps = skps + 1
				time.sleep(0.01)

			diff = SkippedPointCount - countWas

			if (settings.showGUI == True):
				Count2_var.set(str(SkippedPointCount))
			
		if (diff == 0):
			diff = 0
			logging.debug("Retry IRdata Queue")
			IRdataErrFlag = True
			if (settings.showGUI == True):
				Error_var.set("Retry IRdata Queue")
		else:
			if (IRdataErrFlag == True):
				IRdataErrFlag = False
				if (settings.showGUI == True):
					Error_var.set("")

	if (settings.showGUI == True):	
		LastIR_var.set("%0.1f" % ScannerIR)
	
	if (settings.DebugNow == True):
		logging.debug("Exit GetNextTemp #pts: "+ str(diff)+" last: %0.1f" % ScannerIR)

def WaitForDelay():

		RemainingDelay = 0.0  
		
		if (settings.AbortScan == True):
			return
		
		if (settings.DebugNow == True):
			logging.debug("Enter WaitForDelay")   
	
		RemainingDelay = float(settings.StationaryDelay)		#02jul18 TJR
		if (RemainingDelay > 0):	
			time.sleep(RemainingDelay)	

		if (settings.DebugNow == True):
			logging.debug("Exit WaitForDelay delayed: "+str(RemainingDelay))  

def ProcessCrequest(Data, sock=None, Q=None):
	global doingScan
	global lastB1
	global scanningTime
	global minNonScanTemp		#07apr20 TJR
	global InvalidAmbient		#08apr20 TJR

	err = 0
	Msg = ""
	b1 = "" 
	C = 0
	ps = 0					#02nov20 TJR
	eol = 0					#02nov20 TJR
	scanTemp = 0.0			#02nov20 TJR
	xlated = 0.0			#02nov20 TJR
	ErrData = ""
	resp = ""																#26oct20 TJR
	responseS = ""
	responseS2 = ""
	EncodedData = "".encode(encoding='UTF-8') 

	if (Q != None):
		Msg = "Received " + str(len(Data)) +  "bytes"
		Q.put((2,Msg))
																   
	responseS = Data.decode('UTF-8')    
	b1 = responseS[0] 
	logging.debug("processCrequest data: "+responseS+" b1="+b1)                                             
	if (b1 == 'C'):
		ClearScanner()    
		if (settings.serialOpen == True):									#26oct20 TJR
			EncodedData = doComm("C",True)									#28oct20 TJR
		else:  
			ST1 = bytes(str(round(minNonScanTemp,1)),encoding='UTF-8')  	#08apr20 TJR
			if (InvalidAmbient == True):									#08apr20 TJR
				EncodedData = b"+OC,T,"+ST1+b"\n"  							#08apr20 TJR
			else:															#08apr20 TJR
				EncodedData = b"+OC,T,"+ST1+b"\n"   
				debug.LogAction("Current Ambient: %0.1f\n" % minNonScanTemp, True)	#08apr20 TJR            					

		if (sock != None):
			processRecord(EncodedData, sock, Q)                        

		lastB1 = b1

	elif (b1 == 'E'):		
		if (doingScan != constants.fastScanning):
			doingScan = constants.fastScanning

			StartScan = "Aligned"
			if (settings.showGUI == True):
				StartScan_var.set(StartScan)
				StartScanButton.configure(background=constants.LimeGreen_Color)

			ClearScanner()   

			if (settings.serialOpen == True):							#26oct20 TJR
				debug.LogAction("Starting Local Data Scan", True)
				EncodedData = doComm("E",True)							#28oct20 TJR
			else:
				EncodedData = b"+EOk\n"

			if (sock != None):                                                    
				processRecord(EncodedData, sock, Q)                  
															
			if (settings.serialOpen == False):							#26oct20 TJR
				debug.LogAction("Starting Local Data Scan", True)
				scanThread = Thread(target=cmdStart_Scan, name="Scanning", args=(sock, Q,))
				scanThread.setDaemon(True)
				scanThread.start()
				lastB1 = b1  
		else:       
			debug.LogAction("Already Fast Scanning", True)     				#24apr20 TJR                                       																	

	elif (b1 == 'A'):	
		if (settings.serialOpen == True):							#26oct20 TJR
			EncodedData = doComm("A",True)							#28oct20 TJR
		else:														#26oct20 TJR					
			if (doingScan == constants.notScanning):
				debug.LogAction("Abort Scan; Scan Not Active", True)                                     
				EncodedData = b"+ANo\n"
			else:
				doingScan = constants.abortScanning
				debug.LogAction("Abort Active", True)
				EncodedData = b"+AOk\n"

		if (sock != None):                                                    
			processRecord(EncodedData, sock, Q)

		lastB1 = b1                  
															   
	elif (b1 == 'M'):					#Start Normal Scan, Possibly end Fast Scan                             

		#if (doingScan == constants.remoteScanning):
		#	doingScan = constants.doWait
		#
		#	if (settings.serialOpen == True):							#26oct20 TJR
		#		debug.LogAction("Starting Wait for Data", True)
		#		EncodedData = doComm("M",True)							#28oct20 TJR
		#		processRecord(EncodedData, sock, Q)
		#	else:														#26oct20 TJR
		#		debug.LogAction("Starting Wait for Data", True)
		#		Waiting = Thread(target=start_remoteWait, name="Waiting", args=(sock, Q,))
		#		Waiting.setDaemon(True)       
		#		Waiting.start()
			
		if (doingScan == constants.fastScanning):
			if (settings.serialOpen == True):								#26oct20 TJR
				EncodedData = doComm("M",True)								#28oct20 TJR
				if (sock != None):                                  		#03nov20 TJR                  
					processRecord(EncodedData, sock, Q)						#03nov20 TJR

				EncodedData = doComm("",True)								#03nov20 TJR
				responseS = EncodedData.decode('UTF-8') 					#02nov20 TJR
				ps = responseS.find('+S0,0,')								#02nov20 TJR
				eol = responseS.find('\n',ps)								#02nov20 TJR
				scanTemp = float(responseS[ps+6:eol])						#02nov20 TJR
				if (settings.allowXlate == 2):								#02nov20 TJR
					xlated = XlateTemp2(scanTemp)							#02nov20 TJR
				else:														#02nov20 TJR
					xlated = scanTemp										#02nov20 TJR
				responseS2 = responseS[:ps+1] + "P0,0," + str(xlated)		#02nov20 TJR
				responseS2 += responseS[eol:]								#02nov20 TJR

				ps = 0														#03nov20 TJR
				eol = responseS2.find('\n',ps)								#03nov20 TJR
				while (eol > 0):											#03nov20 TJR
					EncodedData = responseS2[ps:eol+1].encode('UTF-8')		#03nov20 TJR
					logging.debug("Will Send: "+str(EncodedData))			#03nov20 TJR
					if (sock != None):                                 		#03nov20 TJR             
						processRecord(EncodedData, sock, Q)					#03nov20 TJR
						time.sleep(0.05)   									#03nov20 TJR
					ps = eol+1												#03nov20 TJR
					eol = responseS2.find('\n',ps)							#03nov20 TJR

				ErrorLabelTag = ""											#26oct20 TJR
				doingScan = constants.notScanning							#26oct20 TJR
				StartScan = "Start Scan"									#26oct20 TJR
				if (settings.showGUI == True):								#26oct20 TJR
					StartScan_var.set(StartScan)							#26oct20 TJR
					StartScanButton.configure(background=constants.MintGreen_Color)	#26oct20 TJR
				settings.ScanComplete = True								#26oct20 TJR
				settings.AbortScan = False									#26oct20 TJR
			else:
				doingScan = constants.stopScanning
				#time.sleep(0.05) 											#15nov20 TJR
				EncodedData = b"+MOk\n"
				if (sock != None):                                                    
					processRecord(EncodedData, sock, Q)
		else:
			if (doingScan == constants.notScanning):					#15feb19 TJR
				doingScan = constants.slowScanning             

				StartScan = "Stop Scan"
				if (settings.showGUI == True):
					StartScan_var.set(StartScan)
					StartScanButton.configure(background=constants.SlateBlue_Color)    

				ClearScanner()   

				if (settings.serialOpen == True):								#26oct20 TJR
					debug.LogAction("Starting Serial Data Scan", True)			#26oct20 TJR
					EncodedData = doComm("M",True)								#28oct20 TJR
					if (sock != None):                                  		#03nov20 TJR                  
						processRecord(EncodedData, sock, Q)						#03nov20 TJR
					
					EncodedData = doComm("",True)								#03nov20 TJR
					responseS = EncodedData.decode('UTF-8') 					#02nov20 TJR
					ps = responseS.find('+S0,0,')								#02nov20 TJR
					eol = responseS.find('\n',ps)								#02nov20 TJR
					scanTemp = float(responseS[ps+6:eol])						#02nov20 TJR
					if (settings.allowXlate == 2):								#02nov20 TJR
						xlated = XlateTemp2(scanTemp)							#02nov20 TJR
					else:														#02nov20 TJR
						xlated = scanTemp										#02nov20 TJR
					xlated = XlateTemp2(scanTemp)								#02nov20 TJR
					responseS2 = responseS[:ps+1] + "P0,0," + str(xlated)		#02nov20 TJR
					responseS2 += responseS[eol:]								#02nov20 TJR
					
					ps = 0														#03nov20 TJR
					eol = responseS2.find('\n',ps)								#03nov20 TJR
					while (eol > 0):											#03nov20 TJR
						EncodedData = responseS2[ps:eol+1].encode('UTF-8')		#03nov20 TJR
						logging.debug("Will Send: "+str(EncodedData))			#03nov20 TJR
						if (sock != None):                                 		#03nov20 TJR             
							processRecord(EncodedData, sock, Q)					#03nov20 TJR
							time.sleep(0.05)   									#03nov20 TJR
						ps = eol+1												#03nov20 TJR
						eol = responseS2.find('\n',ps)							#03nov20 TJR

					ErrorLabelTag = ""											#26oct20 TJR
					doingScan = constants.notScanning							#26oct20 TJR
					StartScan = "Start Scan"									#26oct20 TJR
					if (settings.showGUI == True):								#26oct20 TJR
						StartScan_var.set(StartScan)							#26oct20 TJR
						StartScanButton.configure(background=constants.MintGreen_Color)	#26oct20 TJR
					settings.ScanComplete = True								#26oct20 TJR
					settings.AbortScan = False									#26oct20 TJR
				else:															#26oct20 TJR
					#time.sleep(0.05) 											#15nov20 TJR
					EncodedData = b"+MOk\n"
					if (sock != None):                                                    
						processRecord(EncodedData, sock, Q)

					debug.LogAction("Starting Local Data Scan", True)
					scanThread = Thread(target=cmdStart_Scan, name="Scanning", args=(sock, Q,))
					scanThread.setDaemon(True)       
					scanThread.start()

			else:
				#time.sleep(0.05)												#15nov20 TJR
				EncodedData = b"+MOk\n"
				if (sock != None):                                                    
					processRecord(EncodedData, sock, Q)

				if (doingScan == constants.slowScanning):
					settings.AbortScan = False					# Will Return Data
				else:
					doingScan = constants.abortScanning			# No Data Returned

		lastB1 = b1

	else:
		ErrData = "Invalid Byte 1 (not A,C,E,M): " + responseS
		debug.LogAction(ErrData, True)                                                                       
		EncodedData = b"-" + ErrData.encode(encoding='UTF-8') + b"\n"	
		if (sock != None):                                             
			processRecord(EncodedData, sock, Q)

		ClearScanner()                         
				
def processClient(ip, port, sock, Q):	
	global socketOpen
	global doingScan
	
	logging.debug("Entering processClient")
	
	err = 0
	Msg = ""
	errMsg = ""
	buffer = ''.encode(encoding='UTF-8')   #bytes()
	RetCode = 0

	Msg = "Connection From: "+ip+":"+str(port)
	debug.LogAction(Msg, True)
	logging.debug(Msg)
	socketOpen = True
	Msg = "SocketOpen State: True (processClient)"						#16mar17 TJR
	doprint(Msg)														#22feb19 TJR
	debug.LogAction(Msg, True)											#16mar17 TJR
	logging.debug(Msg)													#16mar17 TJR
	Q.put((1,Msg))
	#sock.timeout = 30
	
	while ((settings.serverRunning == True) and (socketOpen == True)):
		try:
			buffer = sock.recv(settings.TCPIPdataSize)
		except socket.error as e:
			err = e.args[0]
			if ((err == errno.EAGAIN) or (err == errno.EWOULDBLOCK) or (err == errno.ETIMEDOUT)):
				logging.debug("Recoverable Socket Error ("+str(err)+")")
			else:
				logging.debug("Real Socket Error ("+str(err)+")")
				Msg = "Socket Closed"
				Q.put((-1,Msg))
				sock.close()
				socketOpen = False
		except OSError as e:
			err = e.errno
			errMsg = e.strerror
			logging.debug("Socket Bind Error ("+str(err)+"): "+errMsg)
			Msg = "Socket Closed"
			Q.put((-1,Msg))
			sock.close()
			socketOpen = False
		else:
			Msg = "<< ProcessCrequest (" + str(len(buffer)) + ") Received: " + str(buffer)
			debug.LogAction(Msg, True)
			logging.debug(Msg)
			if (len(buffer) == 0):
				Msg = "User Sent No Data: Logoff Signal - Close Socket"
				debug.LogAction(Msg, True)
				logging.debug(Msg)
				Msg = "Socket Closed"
				Q.put((-1,Msg))
				sock.close()
				socketOpen = False
				Msg = "SocketOpen State: False (CLOSED in processClient)"			#16mar17 TJR
				debug.LogAction(Msg, True)											#16mar17 TJR
				logging.debug(Msg)													#16mar17 TJR
			else:
				RetCode = ProcessCrequest(buffer,sock, Q)

	if (doingScan != constants.notScanning):			#24apr20 TJR
		doingScan = constants.abortScanning				#24apr20 TJR
	settings.AbortScan = True							#24apr20 TJR
	time.sleep(0.25)  									#24apr20 TJR
			
	return RetCode
	logging.debug("Exiting processClient")
				
def getConnections(IPaddr, IPport, Q):
	global socketOpen

	err = 0
	errMsg = ""
	
	if (socketOpen == True):
		logging.debug("Starting getConnections socketOpen State: True")
	else:
		logging.debug("Starting getConnections socketOpen State: False")
	
	logging.debug("Attempt to Create Socket: "+IPaddr+":"+str(IPport))
	serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	serverSocket.setblocking(True)
	serverSocket.settimeout(None)
	try:
		serverSocket.bind((IPaddr,IPport))
	except OSError as e:
		err = e.errno
		errMsg = e.strerror
		logging.debug("Socket Bind Error ("+str(err)+"): "+errMsg)
	if (err == 0):
		logging.debug("Socket Created: "+IPaddr+":"+str(IPport))
		Q.put((0,"Server Listening on: "+IPaddr+":"+str(IPport)))
		while (settings.serverRunning == True):
			logging.debug("Socket Listening on: "+IPaddr+":"+str(IPport))
			serverSocket.listen(5)
			try:
				(clientSock, (addr,port)) = serverSocket.accept()				
			except OSError as e:
				err = e.errno
				errMsg = e.strerror
				logging.debug("Listen Error ("+str(err)+"): "+errMsg)
			if (err == 0):
				clientSock.setblocking(True)
				clientSock.settimeout(None)
				client = Thread(target=processClient, name="processSocket", args=(addr, port, clientSock, Q))
				client.setDaemon(True)
				client.start()
	else:
		Q.put((err,errMsg))
	
	serverSocket.close()
	logging.debug("Exiting getConnections - Should Not Happen except on final exit")
	
def msgWatch(Qu):
	global blinkLed1

	err = 0
	errMsg = "" 
	
	logging.debug("Starting msgWatch")
	
	while (settings.serverRunning == True):
		if (Qu.empty() == True):
			time.sleep(0.25)   
		else:
			err,errMsg = Qu.get()
			if (err == 0):
				if (settings.showGUI == True):
					ConnectAddressLabel.configure(bg=constants.PaleGreen_Color)
					c1.itemconfigure(led1,fill=constants.PaleGreen_Color)
				addHistory("* Info: "+errMsg)
			else:
				if (err == 1):
					if (settings.showGUI == True):
						c1.itemconfigure(led1,fill=constants.Green_Color)
					addHistory("* Info: "+errMsg)
				else:
					if (err == 2):
						if (settings.showGUI == True):
							c1.itemconfigure(led1,fill=constants.LimeGreen_Color)
						blinkLed1 = 1
					else:
						if (err == 3):
							if (settings.showGUI == True):
								c1.itemconfigure(led1,fill=constants.Green_Color)
						else:
							if (err == -1):
								if (settings.showGUI == True):
									ConnectAddressLabel.configure(bg=constants.Grey_Color)
									c1.itemconfigure(led1,fill=constants.Grey_Color)
								addException("* "+errMsg)
							else:
								if (settings.showGUI == True):
									ConnectAddressLabel.configure(bg=constants.PaleRed_Color)
									c1.itemconfigure(led1,fill=constants.PaleRed_Color)
								addException("* error ("+str(err)+"): "+errMsg)
								if (settings.showGUI == True):
									Error_var.set(errMsg)

	logging.debug("Exiting msgWatch")
						
def GetScanData():
	global ScannerPointCount
	global ScannerLastIndex
	global ScannerIR
	global peakIRraw
	
	MaxValue = -999.0
	considered = "> "
	p = 0
	total = 0					#16nov20 TJR
	i = ScannerLastIndex # + 1
	while (i <= ScannerPointCount-1):
		total += ScannerPointValue[i]
		considered = considered + str(ScannerPointValue[i]) + ", "
		if (ScannerPointValue[i] > MaxValue):
			MaxValue = ScannerPointValue[i]
		p = p + 1
		i = i + 1

	if (p == 0):
		logging.debug("No IR Scanner Data!!!")
		MaxValue = ScannerIR
	else:
		ScannerLastIndex = ScannerPointCount-1												#16dec16 TJR
		if (settings.UseAvg == True):
			MaxValue = round((total / p),1)

	if (settings.DebugNow == True):
		if (settings.UseAvg == True):
			logging.debug("GetScanData # of Points: " + str(p) + considered + " Avg: %0.1f" % MaxValue)
		else:
			logging.debug("GetScanData # of Points: " + str(p) + considered + " Max: %0.1f" % MaxValue)

	if (MaxValue > peakIRraw):							#17nov20 TJR
		peakIRraw = MaxValue							#17nov20 TJR
		logging.debug("New peakIR: %0.1f" % peakIRraw)	#17nov20 TJR

	return round(MaxValue,1)
	
def XlateTemp2(IrTemp):
	ast = ""
	xlateD = 0.0

	if (IrTemp < settings.TempIn[0]):
		if (settings.ActualOutsideXlate == True):
			xlateD = IrTemp
			ast = " *"
		else:
			xlateD = settings.TempOut[0]
		if (settings.DebugNow == True):
			logging.debug("XlateTemp2 IrTemp: " + str(IrTemp) + " < TempIn[0] " + str(IrTemp) + " = " + str(xlateD)+ast )

	elif (IrTemp > settings.TempIn[settings.xLateTempsCount-1]):
		if (settings.ActualOutsideXlate == True):
			xlateD = IrTemp
			ast = " *"
		else:
			xlateD = settings.TempOut[settings.xLateTempsCount-1]
		if (settings.DebugNow == True):
			logging.debug("XlateTemp2 IrTemp: " + str(IrTemp) + " > TempIn[" + str(settings.xLateTempsCount-1) + "] " + str(IrTemp) + " = " + str(xlateD)+ast )

	else:
		i = 0
		while (IrTemp >= settings.TempIn[i]):
			if (IrTemp == settings.TempIn[i]):
				break
			i += 1

		xlateD = settings.TempOut[i]
		if (settings.DebugNow == True):
			logging.debug("XlateTemp2 IrTemp: " + str(IrTemp) + " > TempIn[" + str(i) + "] " + str(settings.TempIn[i]) + " = " + str(xlateD)+ast )
	
	return xlateD
		
def GetColorIndex(temp):
	idx = 0
	if (settings.OutputValueF == True):
		if (temp > 99):
			return 15
		else:
			idx = int(temp - 85)
			if (idx < 0):
				return 0
			else:
				return idx 
	else: 
		if (settings.OutputValueC == True):
			if (temp > 37.5):
				return 15
			else:
				diff = temp - 30.5
				idx = int(diff * 2)
				if (idx < 0):
					return 0
				else:
					return idx 
		elif (settings.OutputValueK == True):
			if (temp > 310.7):
				return 15
			else:
				diff = temp - 303.7
			idx = int(diff * 2)
			if idx < 0:
				return 0
			else:
				return idx 

def UpdatePoint():				#sets DataPoint to ScannerIR
	global DataPoint
	global peakOut
	global peakIRraw
	
	idx = 0
	bgColor = settings.ColorsRange[idx]
	fgColor = settings.ColorsRange2[idx]
	aMaxChanged = False
	buffer = ""
	
	DataPoint = GetScanData()
	if (DataPoint != -999.0):
		if (settings.allowXlate == 2):
			DataPoint = XlateTemp2(DataPoint)
			
		if (DataPoint > peakOut):
			peakOut = DataPoint

		if (settings.showGUI == True):
			xLated_var.set("%0.1f" % DataPoint)
			xLatedLabel.update()						#05jan17 TJR
					
		if (DataPoint > settings.OverAllMaxPtValue):
			settings.OverAllMaxPtValue = DataPoint
			if (settings.showGUI == True):
				idx = GetColorIndex(DataPoint)
				bgColor = settings.ColorsRange[idx]
				fgColor = settings.ColorsRange2[idx]
				ShowMax_var.set("%0.1f" % DataPoint)
				ShowMaxLabel.configure(bg=bgColor,fg=fgColor)
				ShowMaxLabel.update()					#21dec16 TJR
				ShowMaxIR_var.set("%0.1f" % peakIRraw)
				idx = GetColorIndex(peakIRraw)
				bgColor = settings.ColorsRange[idx]
				fgColor = settings.ColorsRange2[idx]
				ShowMaxIRLabel.configure(bg=bgColor,fg=fgColor)
				ShowMaxIRLabel.update()						#05jan17 TJR

def cmdAmb_Scan():

	logging.debug("cmdAmb_Scan Send: C") 
	ProcessCrequest(b'C',None,None)

def cmdSee_Eye():

	logging.debug("cmdSee_Eye Send: E")  
	ProcessCrequest(b'E',None,None)

def cmdAbort():

	logging.debug("cmdAbort Send: A")  
	ProcessCrequest(b'A',None,None)
	
def cmdStartScan():
    	
	logging.debug("cmdStartScan Send: M")  
	ProcessCrequest(b'M',None,None)

def checkMinMax():
	global peakOut
	global peakIRraw
	global minNonScanTemp 	#07apr20 TJR

	p0 = 0.0
	p1 = 0.0
	LineOut1 = ""
	LineOut1 = "Use Amb Temp %0.1f" % round(minNonScanTemp,1)  						#08apr20 TJR
	debug.LogAction(LineOut1, True)													#21mar19 TJR
	logging.debug(LineOut1) 														#21mar19 TJR
	LineOut1 = "peak IR raw: " + str(peakIRraw)  
	debug.LogAction(LineOut1, True)
	logging.debug(LineOut1)

	if (settings.OutputValueF == True):
		p0 = settings.TempIn[0]
		p1 = settings.TempIn[settings.xLateTempsCount-1]
	elif (settings.OutputValueC == True):
		p0 = round(((settings.TempIn[0]-32)*5)/9,2)
		p1 = round(((settings.TempIn[settings.xLateTempsCount-1]-32)*5)/9,2)
	elif (settings.OutputValueK == True):
		p0 = round(((settings.TempIn[0]+459.67)*5)/9,2)
		p1 = round(((settings.TempIn[settings.xLateTempsCount-1]+459.67)*5)/9,2)

	if (peakIRraw < p0):
		if (settings.ActualOutsideXlate == True):  			         					#30mar20 TJR
			LineOut1 = "Low peak raw: " + str(peakIRraw) + " sending: " + str(peakOut)	#30mar20 TJR
		else:																			#30mar20 TJR
			LineOut1 = "Low peak raw: " + str(peakIRraw) + " sending: 0"
			peakOut = 0.0
	elif (peakIRraw > p1):
		if (settings.ActualOutsideXlate == True):  			         					#30mar20 TJR
			LineOut1 = "High peak raw: " + str(peakIRraw) + " sending: " + str(peakOut)	#30mar20 TJR
		else:																			#30mar20 TJR
			LineOut1 = "High peak raw: " + str(peakIRraw)  + " sending: 0"
			peakOut = 0.0
	else:
		LineOut1 = "peak output: " + str(peakOut)  

	debug.LogAction(LineOut1, True)
	logging.debug(LineOut1)
	LineOut1 = "Max Point: " + str(settings.OverAllMaxPtValue)
	debug.LogAction(LineOut1, True)
	logging.debug(LineOut1) 
	
def cmdStart_Scan(sock=None, Q=None):
	global root
	global doingScan
	global DataPoint
	global ErrorLabelTag
	global ScannerIR
	global peakOut
	global IRdata
	global socketOpen		#15mar17 TJR
	global StartScan
	global scanningTime
	global ScannerPointCount
	global SkippedPointCount
	global minNonScanTemp 	#07apr20 TJR
	global InvalidAmbient	#07apr20 TJR

	logging.debug("Entering cmdStart_Scan")
	err = 0
	errMsg = ""

	T1 = 0.0
	T2 = 0.0
	DataPoint = 0.0
	LineOut1 = ""
	EncodedData = "".encode(encoding='UTF-8') 
	ST1 = b""
	scanningTime = 0.0
	ErrorLabelTag = ""		
	settings.AbortScan = False
	settings.ScanComplete = False
	settings.OverAllMaxPtValue = -999

	if (settings.showGUI == True):
		Count1_var.set(str(ScannerPointCount))
		Count2_var.set(str(SkippedPointCount))
		Count3_var.set(str(scanningTime))
		Count1Label.update()										#16feb19 TJR
		Count2Label.update()										#16feb19 TJR
		Count3Label.update()										#16feb19 TJR
		Error_var.set("")
		ErrorsFrame.configure(background=constants.Grey_Color)
		bgColor = settings.ColorsRange[0]
		fgColor = settings.ColorsRange2[0]
		ShowMaxIR_var.set("")
		ShowMaxIRLabel.configure(bg=constants.Grey_Color)
		ShowMaxIRLabel.update()					#05jan17 TJR
		ShowMax_var.set("")
		ShowMaxLabel.configure(bg=constants.Grey_Color)
		ShowMaxLabel.update()					#21dec16 TJR

	T1 = time.time()
	debug.LogAction("", False)

	IRdata.put(1)		#Starts Queueing temps 
	WaitForDelay()
	UpdatePoint()		#28dec16 TJR			

	WriteDataFile() 
		
	if (settings.AbortScan == False):
		while (DataPoint != -999.0):
			WaitForDelay()

			UpdatePoint()
			T2 = time.time()												#15feb19 TJR
			scanningTime = round(T2-T1,1)									#15feb19 TJR
			if (DataPoint != -999.0):
				WriteDataFile() 
				if (settings.showGUI == True):
					root.update_idletasks()
					Count1_var.set(str(ScannerPointCount))
					Count2Label.update()									#16feb19 TJR
					Count3_var.set(str(scanningTime))						#16feb19 TJR
					Count3Label.update()									#16feb19 TJR

			if (doingScan == constants.abortScanning):						#15feb19 TJR
				break														#15feb19 TJR
			elif (doingScan == constants.slowScanning):						#15feb19 TJR
				if (scanningTime > float(settings.StationaryScanTime)):		#15feb19 TJR
					break													#15feb19 TJR
			elif (doingScan == constants.stopScanning):						#15feb19 TJR
				if (scanningTime > (float(settings.StationaryScanTime)+1)):	#15feb19 TJR
					break													#15feb19 TJR
			elif (doingScan == constants.fastScanning):						#15feb19 TJR
				scanningTime += 0   #Keep Waiting							#15feb19 TJR
								
	settings.ScanComplete = True
	IRdata.put(0)                   #16dec16 TJR

	if (settings.showGUI == True):
		Count2_var.set(str(SkippedPointCount))

	if (doingScan != constants.abortScanning):
		if (settings.AbortScan == False):
			ST1 = bytes(str(round(scanningTime,1)),encoding='UTF-8')
			LineOut1 = "Run Time %0.1f s" % (scanningTime)
			if (settings.showGUI == True):
				Error_var.set(LineOut1)
			debug.LogAction(LineOut1, True)
			logging.debug(LineOut1) 

			checkMinMax()								#13nov20 TJR

			EncodedData = b"*Run Time "+ST1+b" s\n"
			sendResults(EncodedData, sock, Q)    
					
		else:
			if (settings.showGUI == True):
				Error_var.set("Aborted %0.1f s" % (T2 - T1))
			debug.LogAction("Abort %0.1f s" % (T2 - T1), True)
			
			if (socketOpen == False):
				LineOut1 = "socketOpen: False - Abort Cmd (cmdStart_Scan)"
				doprint(LineOut1)
				debug.LogAction(LineOut1, True)
				logging.debug(LineOut1)
			else:
				ST1 = bytes(str(round(T2 - T1,1)),encoding='UTF-8')
				EncodedData = b"-Aborted "+ST1+b" s \n"
				processRecord(EncodedData, sock, Q)  
				LineOut1 = "Scan Aborted, Sent Abort Notification"
				debug.LogAction(LineOut1, True)
				logging.debug(LineOut1)
			
		if (settings.showGUI == True):
			ErrorsFrame.configure(background=constants.Grey_Color)
	else:
		if (socketOpen == False):
			LineOut1 = "Abort Cmd socketOpen: False - ? (cmdStart_Scan)"
			doprint(LineOut1)
			debug.LogAction(LineOut1, True)
			logging.debug(LineOut1)
		else:
			LineOut1 = "Abort Cmd socketOpen: True - OK (cmdStart_Scan)"
			doprint(LineOut1)
			debug.LogAction(LineOut1, True)
			logging.debug(LineOut1)

	ErrorLabelTag = ""
	doingScan = constants.notScanning					#15feb19 TJR
	StartScan = "Start Scan"							#06jul18 TJR
	if (settings.showGUI == True):
		StartScan_var.set(StartScan)
		StartScanButton.configure(background=constants.MintGreen_Color)			

	settings.AbortScan = False
	logging.debug("Exiting cmdStart_Scan")

def start_remoteWait(sock=None, Q=None):
	global doingScan
	global ErrorLabelTag
	global peakOut
	global socketOpen		
	global StartScan
	global scanningTime

	doprint("Entering start_remoteWait")
	err = 0
	errMsg = ""

	T1 = 0.0
	T2 = 0.0
	LineOut1 = ""
	EncodedData = "".encode(encoding='UTF-8') 
	ST1 = b""
	waitingTime = 0.0

	T1 = time.time()
	debug.LogAction("", False)
	WriteDataFile() 				#write intermediate results

	while (doingScan == constants.doWait):
		time.sleep(0.01)
		T2 = time.time()												
		waitingTime = round(T2-T1,1)	

	if doingScan == constants.doReporting:	
		ST1 = bytes(str(round(scanningTime,1)),encoding='UTF-8')
		LineOut1 = "Run Time %0.1f s" % (scanningTime)
		if (settings.showGUI == True):
			Error_var.set(LineOut1)
		debug.LogAction(LineOut1, True)
		logging.debug(LineOut1) 

		checkMinMax()								#13nov20 TJR

		EncodedData = b"*Run Time "+ST1+b" s\n"
		sendResults(EncodedData, sock, Q)    

	else:
		if (socketOpen == False):
			LineOut1 = "Abort Wait socketOpen: False - ? (start_remoteWait)"
			doprint(LineOut1)
			debug.LogAction(LineOut1, True)
			logging.debug(LineOut1)
		else:
			LineOut = "Abort Wait socketOpen: True - OK (start_remoteWait)"
			doprint(LineOut1)
			debug.LogAction(LineOut1, True)
			logging.debug(LineOut1)

	settings.ScanComplete = True
	settings.AbortScan = False
	WriteDataFile() 					#write final results
	doingScan = constants.notScanning				

	ErrorLabelTag = ""
	StartScan = "Start Scan"							
	if (settings.showGUI == True):
		StartScan_var.set(StartScan)
		StartScanButton.configure(background=constants.MintGreen_Color)			
		ErrorsFrame.configure(background=constants.Grey_Color)

	doprint("Exiting start_remoteWait waited for: "+str(waitingTime))

def ClearScanner():
	global scanning
	global queueIRdata
	global ScannerIR
	global ScannerIRraw				#07apr29 TJR
	global ScannerLastIndex
	global ScannerPointCount
	global SkippedPointCount
	global ResetLastIndex
	global ScannerPointValue
	global peakOut
	global peakIRraw
	
	logging.debug("Entering Clear Scanner")

	ScannerIR = -999.0
	ScannerIRraw = -999.0				#07apr29 TJR
	SkippedPointCount = 0
	ScannerPointCount = 0
	ResetLastIndex = True
	ScannerPointValue = []
	peakOut = -999.0
	peakIRraw = -999.0
	settings.ssTemp = -999.0
	queueIRdata = False
	if (settings.showGUI == True):
		ShowMaxIR_var.set("")					#05jan17 TJR
		ShowMaxIRLabel.update()					#05jan17 TJR
		ShowMax_var.set("")						#05jan17 TJR
		ShowMaxLabel.update()					#05jan17 TJR
	
		Count1_var.set(str(ScannerPointCount))
		Count2_var.set(str(SkippedPointCount))
		Count3_var.set(str(0.0))

		LastIR_var.set('')
		xLated_var.set('')
		LastIRLabel.update()		#21dec16 TJR
		xLatedLabel.update()		#21dec16 TJR

	logging.debug("Exiting Clear Scanner")	
	
def mainTick():	
	global doingScan
	global countMinScanTemps
	global minNonScanTemp
	global secondCnt
	global ScannerIRraw				#07apr20 TJR
	global avgAmbientPoints			#08may20 TJR
	global avgAmbientTotal			#08may20 TJR

	avgAmbient = 0.0
	if (doingScan == constants.notScanning):							#21mar19 TJR
		getIRpoint()													#09apr20 TJR
		if (ScannerIRraw != -999.0):										#21mar19 TJR
			countMinScanTemps += 1										#21mar19 TJR
			avgAmbientPoints += 1										#08may20 TJR
			avgAmbientTotal += ScannerIRraw								#08may20 TJR
			if (ScannerIRraw < minNonScanTemp):							#21mar19 TJR
				updateAmbient(ScannerIRraw, True)						#09apr20 TJR				
			elif countMinScanTemps > 300:								#08apr20 TJR
				avgAmbient = avgAmbientTotal / avgAmbientPoints			#08may20 TJR
				logging.debug('Avg Ambient over 5m: %0.1fF' % avgAmbient)
				avgAmbientPoints = 0									#08may20 TJR
				avgAmbientTotal = 0										#08may20 TJR				
#				if abs(minNonScanTemp - ScannerIRraw) <= 6:				#21mar19 TJR
#					newAvgMinTemp = (minNonScanTemp + ScannerIRraw) / 2 #08apr20 TJR
				updateAmbient(avgAmbient, True)							#08may20 TJR
				countMinScanTemps = 1									#21mar19 TJR

	if (settings.showGUI == True) :				#09jul18 TJR
		SecondsRun_var.set(str(secondCnt))
		SecondsRun_label.update()
		if (settings.serverRunning == True):
			root.after(1000,mainTick)

def main(args):
	
	return 0

if __name__ == '__main__':
	#global sT0
	#global msT0
	#global Qusers
	#global IRdata
	#global getIR
	#global serData 				#27oct20 TJR
	#global watcher
	#global root
	
	myName = "Maestro3"
	ports = ""
	message = ""
	Msg = ""
	settings.init()

	time.sleep(settings.d0)		# Delay this long before Starting
	logging.debug("Starting: "+myName)
	settings.myPath = abspath(getsourcefile(lambda:0)).replace(myName+'.py','')     #getHome()
	message = settings.preReadConfig(myName)
	if len(message) > 0:
		logging.debug(message)
	else:
		if (settings.consoleOutput == True):
			logging.debug(".cfg = "+settings.configFileName)
			if (settings.haveIni == True):
				logging.debug('.ini = '+settings.iniFileName)
			else:
				logging.debug("No .ini File ('+settings.iniFileName+') found.")

	if (settings.showGUI == True):
		root = tk.Tk()
		#if settings.consoleOutput == False:
		#	root.withdraw()
			
		root.geometry('420x210+5+5')
		root.wm_title(myName)
		xMax = 420
		yMax = 180  #410
		nb = ttk.Notebook(root,height=yMax,width=xMax)
		s = ttk.Style()
		s.configure('.',font=('Small Fonts', 7))
		s.configure('Tab1.TFrame',background=constants.Grey_Color,font=('Small Fonts', 7))
		s.configure('Tab2.TFrame',background=constants.LightGrey_Color,font=('Small Fonts', 7))
		s.configure('Tab3.TFrame',background=constants.CyanGrey_Color,font=('Small Fonts', 7))
		nb.enable_traversal()
		page1 = ttk.Frame(nb,style='Tab1.TFrame')
		page2 = ttk.Frame(nb,style='Tab2.TFrame')
		page3 = ttk.Frame(nb,style='Tab3.TFrame')

		nb.add(page1, text="Scans")
		nb.add(page2, text="Errs")
		nb.add(page3, text="History")
		nb.pack()
		
		c1 = tk.Canvas(page1, bg=constants.Grey_Color,height=18,width=18,bd=1,highlightthickness=0,relief='sunken')
		led1 = c1.create_oval(2,2,16,16,outline=constants.Green_Color,fill=constants.PaleGreen_Color)

		StartLabel = tk.Label(page1,text="Waiting for Signal to Start",font=("Small Fonts", 7),bg=constants.Cyan_Color,justify=tk.LEFT,anchor=tk.W)
		c0 = tk.Canvas(StartLabel, bg=constants.Grey_Color,height=14,width=14,bd=1,highlightthickness=0,relief='sunken')
		led0 = c0.create_oval(2,2,12,12,outline=constants.Green_Color,fill=constants.PaleGreen_Color)
		
		w = 20
		h = 20
		x = xMax-w-4
		y = 1
		c1.place(x=x,y=y,width=w,height=h)
		
		y = 1
		w = 145
		x = x - w - 5
		StartLabel.place(x=x,y=y,width=w,height=h)
		
		x = w - 15
		w = 16
		y = 1
		h = 16
		c0.place(x=x,y=y,width=w,height=h)
					    
		AmbScan_var = tk.StringVar(value="Amb Scan")
		AmbScanButton = tk.Button(page1, textvariable=AmbScan_var,font=("Small Fonts", 7),bg=constants.MintGreen_Color, command=cmdAmb_Scan)
		seeEye_var = tk.StringVar(value="See Eyes")
		SeeEyeButton = tk.Button(page1, textvariable=seeEye_var,font=("Small Fonts", 7),bg=constants.MintGreen_Color, command=cmdSee_Eye)
		Abort_var = tk.StringVar(value="Abort")
		AbortButton = tk.Button(page1, textvariable=Abort_var,font=("Small Fonts", 7),bg=constants.MintGreen_Color, command=cmdAbort)
		Count3_var = tk.StringVar(value="")
		Count3Label = tk.Label(page1,textvariable=Count3_var,bg=constants.Grey_Color,bd=1,relief='sunken',anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 7))

		StartScan = "Start Scan"
		StartScan_var = tk.StringVar(value=StartScan)
		StartScanButton = tk.Button(page1, textvariable=StartScan_var,font=("Small Fonts", 7),bg=constants.MintGreen_Color, command=cmdStartScan)
		ShowMax_label = tk.Label(page1,text="Max IR/Xlate",font=("Small Fonts", 7),bg=constants.Grey_Color,anchor=tk.W)
		ShowMaxIR_var = tk.StringVar(value="")
		ShowMaxIRLabel = tk.Label(page1,textvariable=ShowMaxIR_var,bg=constants.Grey_Color,fg=constants.Grey_Color,bd=1,relief='sunken',anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 7))
		ShowMax_var = tk.StringVar(value="")
		ShowMaxLabel = tk.Label(page1,textvariable=ShowMax_var,bg=constants.Grey_Color,fg=constants.Grey_Color,bd=1,relief='sunken',anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 7))
		Count_label = tk.Label(page1,text="Counted/Skip",font=("Small Fonts", 7),bg=constants.Grey_Color,anchor=tk.W)
		Count1_var = tk.StringVar(value="")
		Count1Label = tk.Label(page1,textvariable=Count1_var,bg=constants.Grey_Color,bd=1,relief='sunken',anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 7))
		Count2_var = tk.StringVar(value="")
		Count2Label = tk.Label(page1,textvariable=Count2_var,bg=constants.Grey_Color,bd=1,relief='sunken',anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 7))
		
		Started_label = tk.Label(page1,text="Started",font=("Small Fonts", 7),bg=constants.Grey_Color,anchor=tk.W)
		Started_var = tk.StringVar(value="")
		StartedLabel = tk.Label(page1,textvariable=Started_var,bg=constants.Grey_Color,bd=1,relief='sunken',anchor=tk.W,justify=tk.LEFT,font=("Small Fonts", 7))
		SecondsRunlabel = tk.Label(page1,text="Seconds Run",anchor=tk.E,justify=tk.RIGHT,bg=constants.Grey_Color,font=("Small Fonts", 7))
		SecondsRun_var = tk.StringVar(value="0")
		SecondsRun_label = tk.Label(page1,textvariable=SecondsRun_var,bd=1,relief='sunken',anchor=tk.E,justify=tk.RIGHT,bg=constants.Silver_Color,font=("Small Fonts", 7))
		#Ambient_label = tk.Label(page1,text="Last Sensor/Amb Temp",font=("Small Fonts", 7),bg=constants.Grey_Color,anchor=tk.E)
		Ambient_label = tk.Label(page1,text="Ambient Temp",font=("Small Fonts", 7),bg=constants.Grey_Color,anchor=tk.E)
		#Ambient_var = tk.StringVar(value="")
		#AmbientLabel = tk.Label(page1,textvariable=Ambient_var,bg=constants.Grey_Color,bd=1,relief='sunken',anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 7))

		AmbientX_var = tk.StringVar(value="")
		AmbientXLabel = tk.Label(page1,textvariable=AmbientX_var,bg=constants.Grey_Color,bd=1,relief='sunken',anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 7))

		LastIR_label = tk.Label(page1,text="Last IR Temp",font=("Small Fonts", 7),bg=constants.Grey_Color,anchor=tk.E)
		LastIR_var = tk.StringVar(value="")
		LastIRLabel = tk.Label(page1,textvariable=LastIR_var,bg=constants.Grey_Color,bd=1,relief='sunken',anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 7))
		xLated_label = tk.Label(page1,text="Last xLated Temp",font=("Small Fonts", 7),bg=constants.Grey_Color,anchor=tk.E)
		xLated_var = tk.StringVar(value="")
		xLatedLabel = tk.Label(page1,textvariable=xLated_var,bg=constants.Grey_Color,bd=1,relief='sunken',anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 7))

		aScale = []
		aScale.append(tk.Label(page1,text="<84",bg=constants.DarkGrey_Color,fg=constants.Black_Color,anchor=tk.E,justify=tk.CENTER,font=("Small Fonts", 6)))
		aScale.append(tk.Label(page1,text="85",bg=constants.DarkGrey_Color,fg=constants.Black_Color,anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 6)))
		aScale.append(tk.Label(page1,text="86",bg=constants.DarkGrey_Color,fg=constants.Black_Color,anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 6)))		
		aScale.append(tk.Label(page1,text="87",bg=constants.DarkGrey_Color,fg=constants.Black_Color,anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 6)))
		aScale.append(tk.Label(page1,text="88",bg=constants.DarkGrey_Color,fg=constants.Black_Color,anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 6)))
		aScale.append(tk.Label(page1,text="89",bg=constants.DarkGrey_Color,fg=constants.Black_Color,anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 6)))
		aScale.append(tk.Label(page1,text="90",bg=constants.DarkGrey_Color,fg=constants.Black_Color,anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 6)))
		aScale.append(tk.Label(page1,text="91",bg=constants.DarkGrey_Color,fg=constants.Black_Color,anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 6)))
		aScale.append(tk.Label(page1,text="92",bg=constants.DarkGrey_Color,fg=constants.Black_Color,anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 6)))
		aScale.append(tk.Label(page1,text="93",bg=constants.DarkGrey_Color,fg=constants.Black_Color,anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 6)))
		aScale.append(tk.Label(page1,text="94",bg=constants.DarkGrey_Color,fg=constants.Black_Color,anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 6)))
		aScale.append(tk.Label(page1,text="95",bg=constants.DarkGrey_Color,fg=constants.White_Color,anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 6)))
		aScale.append(tk.Label(page1,text="96",bg=constants.DarkGrey_Color,fg=constants.White_Color,anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 6)))
		aScale.append(tk.Label(page1,text="97",bg=constants.DarkGrey_Color,fg=constants.White_Color,anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 6)))
		aScale.append(tk.Label(page1,text="98",bg=constants.DarkGrey_Color,fg=constants.White_Color,anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 6)))
		aScale.append(tk.Label(page1,text=">99",bg=constants.DarkGrey_Color,fg=constants.White_Color,anchor=tk.E,justify=tk.RIGHT,font=("Small Fonts", 6)))	

		OptionFrame = tk.Label(page1,text="Options",bg=constants.Grey_Color,bd=1,relief='sunken',anchor=tk.NW,justify=tk.LEFT,font=("Small Fonts", 7))
		InfoFrame = tk.Label(page1,text="Info",bg=constants.Grey_Color,bd=1,relief='sunken',anchor=tk.NW,justify=tk.LEFT,font=("Small Fonts", 7))
		ErrorsFrame = tk.Label(page1,text="Errors",bg=constants.Grey_Color,bd=1,relief='sunken',anchor=tk.NW,justify=tk.LEFT,font=("Small Fonts", 7))
		Error_var = tk.StringVar(value="")
		ErrorLabel = tk.Label(ErrorsFrame,textvariable=Error_var,bg=constants.LightYellow_Color,bd=1,relief='sunken',anchor=tk.W,justify=tk.LEFT,font=("Small Fonts", 7))
		
		w = 35
		x = xMax - w - 100
		y = 24
		h = 15
		Started_label.place(x=x,y=y,width=w,height=h)
		w = 90
		x = xMax - w - 6
		StartedLabel.place(x=x,y=y,width=w,height=h)
		y = y + 21
		w = 75
		x = xMax - w - 36
		SecondsRunlabel.place(x=x,y=y,width=w,height=h)
		w = 30
		x = xMax - w - 6
		SecondsRun_label.place(x=x,y=y,width=w,height=h)
		y = y + 18
		w = 110
		x = xMax - 40 - 136
		Ambient_label.place(x=x+25,y=y,width=w,height=h)
		x = x + 35
		w = 100
		y = y + 18
		LastIR_label.place(x=x,y=y,width=w,height=h)
		y = y + 18
		xLated_label.place(x=x,y=y,width=w,height=h)
		y = y - 36
		w = 30
		x = xMax - w - 37
		#AmbientLabel.place(x=x,y=y,width=w,height=h)
		x = xMax - w - 6
		AmbientXLabel.place(x=x,y=y,width=w,height=h)
		y = y + 18
		LastIRLabel.place(x=x,y=y,width=w,height=h)
		y = y + 18
		xLatedLabel.place(x=x,y=y,width=w,height=h)
		y = y + 18
		w = 154		
		x = xMax - w - 10
		AmbScanButton.place(x=x,y=y,width=53,height=h)
		x = x + 57
		StartScanButton.place(x=x,y=y,width=101,height=h)
		y = y + 18
		x = x - 62
		Count_label.place(x=x,y=y,width=60,height=h)
		x = x + 65
		w = 50
		Count1Label.place(x=x,y=y,width=w,height=h)
		x = x + 50
		Count2Label.place(x=x,y=y,width=w,height=h)
		y = y + 18
		x = x - 111
		w = 60	
		ShowMax_label.place(x=x,y=y,width=w,height=h)
		x = x + w 
		w = 50
		ShowMaxIRLabel.place(x=x,y=y,width=w,height=h)
		x = x + 53
		ShowMaxLabel.place(x=x,y=y,width=w,height=h)
		y = y + 18
		h = 10
		w = 18
		x = xMax-3-w
		aScale[15].place(x=x,y=y,width=w,height=h)
		w = 16
		x = x - w
		aScale[14].place(x=x,y=y,width=w,height=h)
		x = x - w
		aScale[13].place(x=x,y=y,width=w,height=h)
		x = x - w
		aScale[12].place(x=x,y=y,width=w,height=h)
		x = x - w
		aScale[11].place(x=x,y=y,width=w,height=h)
		x = x - w
		aScale[10].place(x=x,y=y,width=w,height=h)
		x = x - w
		aScale[9].place(x=x,y=y,width=w,height=h)
		x = x - w
		aScale[8].place(x=x,y=y,width=w,height=h)
		x = x - w
		aScale[7].place(x=x,y=y,width=w,height=h)
		x = x - w
		aScale[6].place(x=x,y=y,width=w,height=h)
		x = x - w
		aScale[5].place(x=x,y=y,width=w,height=h)
		x = x - w
		aScale[4].place(x=x,y=y,width=w,height=h)
		x = x - w
		aScale[3].place(x=x,y=y,width=w,height=h)
		x = x - w
		aScale[2].place(x=x,y=y,width=w,height=h)
		x = x - w
		aScale[1].place(x=x,y=y,width=w,height=h)
		x = x - w
		aScale[0].place(x=x,y=y,width=w,height=h)
		y = y - 5
		h = 15
		x = 5
		w = 50		
		SeeEyeButton.place(x=x,y=y,width=w,height=h)
		w = 40	
		x = x + 55
		AbortButton.place(x=x,y=y,width=w,height=h)
		x = x + 45
		w = 35
		Count3Label.place(x=x,y=y,width=w,height=h)

		x = 3
		y = 3
		w = 245
		h = 55
		OptionFrame.place(x=x,y=y,width=w,height=h)
		StationaryDelay_label = tk.Label(OptionFrame,text="Stationary Delay",bg=constants.Grey_Color,font=("Small Fonts", 7))
		StationaryDelay_var = tk.StringVar(value="")
		StationaryDelayLabel = tk.Entry(OptionFrame,textvariable=StationaryDelay_var,bg=constants.Grey_Color,bd=1,relief='sunken',justify=tk.RIGHT,font=("Small Fonts", 7),validate='focusout',validatecommand=doStationaryDelay,state='disabled')
		StationaryScanTime_label = tk.Label(OptionFrame,text="Scan Time",bg=constants.Grey_Color,font=("Small Fonts", 7))
		StationaryScanTime_var = tk.StringVar(value="")
		StationaryScanTimeLabel = tk.Entry(OptionFrame,textvariable=StationaryScanTime_var,bg=constants.Grey_Color,bd=1,relief='sunken',justify=tk.RIGHT,font=("Small Fonts", 7),validate='focusout',validatecommand=doStationaryScanTime,state='disabled')

		Xlate2_var = tk.IntVar(value=0)
		Xlate2_Check = tk.Checkbutton(OptionFrame,text="xLate2 Output",variable=Xlate2_var,bg=constants.Grey_Color,anchor=tk.W,justify=tk.LEFT,font=("Small Fonts", 7), command=doXlate1)
		WriteLog_var = tk.IntVar(value=0)
		WriteLog_Check = tk.Checkbutton(OptionFrame,text="Write Log",variable=WriteLog_var,bg=constants.Grey_Color,anchor=tk.W,justify=tk.LEFT,font=("Small Fonts", 7), command=doLog)
		WriteData_var = tk.IntVar(value=0)
		WriteData_Check = tk.Checkbutton(OptionFrame,text="Write Data",variable=WriteData_var,bg=constants.Grey_Color,anchor=tk.W,justify=tk.LEFT,font=("Small Fonts", 7), command=doData)

		y = y + h + 5
		h = 75
		InfoFrame.place(x=x,y=y,width=w,height=h)
		ConnectAddress_label = tk.Label(InfoFrame,text="Connect To:",font=("Small Fonts", 7),bg=constants.Grey_Color,anchor=tk.W,justify=tk.LEFT)
		ConnectAddress_var = tk.StringVar(value="")
		ConnectAddressLabel = tk.Label(InfoFrame,textvariable=ConnectAddress_var,bg=constants.Grey_Color,bd=1,relief='sunken',anchor=tk.W,justify=tk.LEFT,font=("Small Fonts", 7))
		PauseButton = tk.Button(InfoFrame, text="Pause",font=("Small Fonts", 7), command=doPause)
		QuitButton = tk.Button(InfoFrame, text="Quit",font=("Small Fonts", 7), command=doExit)
		AboutButton = tk.Button(InfoFrame, text="About",font=("Small Fonts", 7), command=doAbout)
		WaitingLabel_var = tk.StringVar(value="Waiting")
		WaitingLabel = tk.Label(InfoFrame,textvariable=WaitingLabel_var,bg=constants.Grey_Color,bd=1,relief='sunken',justify=tk.CENTER,font=("Small Fonts", 7))

		LogFile_var = tk.StringVar(value="")
		LogFileLabel = tk.Label(InfoFrame,textvariable=LogFile_var,bg=constants.Cream_Color,bd=1,relief='sunken',anchor=tk.W,justify=tk.LEFT,font=("Small Fonts", 7))
		y = y + h + 5
		h = 20
		ErrorsFrame.place(x=x,y=y,width=w,height=h)
		x = 35
		y = 2
		h = 14
		w = 205
		ErrorLabel.place(x=x,y=y,width=w,height=h)
		
		AboutFrame = tk.Label(page1,text="",bg=constants.Smoke_Color,bd=1,relief='raise',anchor=tk.E,justify=tk.LEFT,font=("Arial", 8))
		AboutFrame.bind("<Button-1>",doAbout2)	
		About1_var = tk.StringVar(value="WelloCL")
		About1Label = tk.Label(AboutFrame,textvariable=About1_var,bg=constants.Grey_Color,justify=tk.CENTER,font=("Arial", 8, "bold"))
		About1Label.bind("<Button-1>",doAbout2)	
		About2_var = tk.StringVar(value="All about me")
		About2Label = tk.Label(AboutFrame,textvariable=About2_var,bg=constants.Smoke_Color,bd=1,relief='sunken',anchor=tk.N,justify=tk.LEFT,font=("Small Fonts", 7),wraplength=230)
		About2Label.bind("<Button-1>",doAbout2)	
	
		h = 15
		x = 3
		y = y + h
		w = 68
		StationaryDelay_label.place(x=x,y=y,width=w,height=h)
		x = x + w + 3
		w = 25
		StationaryDelayLabel.place(x=x,y=y,width=w,height=h)
		x = x + w + 2
		w = 45
		StationaryScanTime_label.place(x=x,y=y,width=w,height=h)
		x = x + w + 2
		w = 20
		StationaryScanTimeLabel.place(x=x,y=y,width=w,height=h)
		x = x + w + 2
		w = 70
		WriteData_Check.place(x=x,y=y,width=w,height=h)

		x = 3
		y = y + h + 3
		w = 80
		Xlate2_Check.place(x=x,y=y,width=w,height=h)		#03jan16 TJR
		x = x + w + 10
		w = 70
		WriteLog_Check.place(x=x,y=y,width=w,height=h)	
		x = 3
		h = 15
		w = 60
		y = 13
		ConnectAddress_label.place(x=x,y=y,width=w,height=h)
		x = x + w
		w = 245-w-5
		ConnectAddressLabel.place(x=x,y=y,width=w,height=h)
		y = y + h + 5
		x = 3
		w = 60
		h = 15
		PauseButton.place(x=x,y=y,width=w,height=h)
		x = x + w + 5
		QuitButton.place(x=x,y=y,width=w,height=h)
		x = x + w + 5
		AboutButton.place(x=x,y=y,width=w,height=h)
		x = x + w + 5
		w = 43
		WaitingLabel.place(x=x,y=y,width=w,height=h)
		y = y + h + 5
		x = 2
		w = 245 - 8
		LogFileLabel.place(x=x,y=y,width=w,height=h)
		#logging.debug("YMax="+str(y+h))
		
		h = 90
		w = 240
		x = 5
		y = 20
		settings.showingAbout = y
		AboutFrame.place(x=x,y=y,width=w,height=h)
		x = 5
		y = 2
		w = 230
		h = 15
		About1Label.place(x=x,y=y,width=w,height=h)
		x = 5
		y = y + h + 2
		h = 90 - y - 5
		About2Label.place(x=x,y=y,width=w,height=h)
		AboutFrame.lift()		# keep on top
		# now hide it
		doAbout()

		exceptionList = tk.Listbox(page2, width=60, height=12, selectmode=tk.BROWSE,font=("Small Fonts", 7))
		historyList = tk.Listbox(page3, width=60, height=12, selectmode=tk.BROWSE, font=("Small Fonts", 7))
		x = 5
		y = 5
		w = xMax - x - 5
		h = 180 - y
		exceptionList.place(x=x,y=y,width=w,height=h)
		historyList.place(x=x,y=y,width=w,height=h)

	now = datetime.datetime.today()	
	
	addHistory("Home Directory is: "+settings.myPath)
	addHistory("User: "+getUser())
	settings.osName = os.name
	settings.localName = socket.gethostname()
	settings.localIP = socket.gethostbyname(settings.localName)
	addHistory("OS: "+settings.osName)
	addHistory("Local Name: "+settings.localName+" Local IP address: "+settings.localIP)
	
	readConfig()

	if (len(settings.serialPort) > 0):
		ports = serial_ports()
		if (len(ports) > 0):
			try:
				i = ports.index(settings.serialPort)
			except ValueError:
				i = -1
				pass

			if (i < 0):
				logging.debug("Requested comm port(" +settings.serialPort + ") not available.")
			else:
				logging.debug("Comm port(" +settings.serialPort + ") available.")
				try:
					#ser = serial.Serial(port=settings.serialPort,baudrate=settings.serialBaud)
					ser = serial.Serial(port=settings.serialPort,baudrate=settings.serialBaud,parity=settings.serialParity,bytesize=settings.serialBits,stopbits=settings.serialStopBits,timeout=1)
					#ser = serial.Serial(port=settings.serialPort,baudrate=settings.serialBaud,timeout=1,write_timeout=0)
				except OSError as e:
					settings.serialOpen = False
					pass
				except serial.SerialException:
					settings.serialOpen = False
					pass
				else:
					ser.flush()
					settings.serialOpen = True
					logging.debug("Comm port: "+settings.serialPort+ " Opened")
					time.sleep(0.5)	
		else:
			logging.debug("No comm ports available.")
			settings.serialOpen = False

#if (settings.testing == False) and (settings.serialOpen == False):
	import Melexis							

	if (settings.showGUI == True):
		logging.debug("GUI Built: "+now.strftime(settings.EPdateTimeFormat))
		SecondsRun_var.set(str(secondCnt))
		# .ini settings
		if (settings.allowXlate == 0):
			Xlate2_var.set(0)
		else:
			Xlate2_var.set(1)
		WriteData_var.set(settings.DataCheck)
		WriteLog_var.set(settings.LogCheck)
		StationaryDelay_var.set(str(settings.StationaryDelay))
		StationaryScanTime_var.set(str(settings.StationaryScanTime))

		#.cfg settings
		About1_var.set(settings.Header)
		About2_var.set(settings.What)
		#ComputerName_var.set(settings.localName)
		ConnectAddress_var.set(settings.TCPIPinAddr+":"+str(settings.TCPIPinPort))
		if len(settings.LogFile) > 0:
			LogFile_var.set(settings.LogFile)
		else:
			LogFile_var.set("> Not Logging <")
		Started_var.set(now.strftime(settings.EPdateTimeFormat))
		i = 0
		while i < 16:
			aScale[i].configure(bg=settings.ColorsRange[i],fg=settings.ColorsRange2[i])
			i = i + 1
		if (settings.OutputValueF == True):
			aScale[0].configure(text="<84")
			aScale[1].configure(text="85")
			aScale[2].configure(text="86")		
			aScale[3].configure(text="87")
			aScale[4].configure(text="88")
			aScale[5].configure(text="89")
			aScale[6].configure(text="90")
			aScale[7].configure(text="91")
			aScale[8].configure(text="92")
			aScale[9].configure(text="93")
			aScale[10].configure(text="94")
			aScale[11].configure(text="95")
			aScale[12].configure(text="96")
			aScale[13].configure(text="97")
			aScale[14].configure(text="98")
			aScale[15].configure(text=">99")	
		elif (settings.OutputValueC == True):
			aScale[0].configure(text="<30")
			aScale[1].configure(text="30.5")
			aScale[2].configure(text="31")		
			aScale[3].configure(text="31.5")
			aScale[4].configure(text="32")
			aScale[5].configure(text="32.5")
			aScale[6].configure(text="33")
			aScale[7].configure(text="33.5")
			aScale[8].configure(text="34")
			aScale[9].configure(text="34.5")
			aScale[10].configure(text="35")
			aScale[11].configure(text="35.5")
			aScale[12].configure(text="36")
			aScale[13].configure(text="36.5")
			aScale[14].configure(text="37")
			aScale[15].configure(text=">37.5")	
		elif (settings.OutputValueK == True):
			aScale[0].configure(text="<303")
			aScale[1].configure(text="303.7")
			aScale[2].configure(text="304")		
			aScale[3].configure(text="304.7")
			aScale[4].configure(text="305")
			aScale[5].configure(text="305.7")
			aScale[6].configure(text="306")
			aScale[7].configure(text="306.7")
			aScale[8].configure(text="307")
			aScale[9].configure(text="307.7")
			aScale[10].configure(text="308")
			aScale[11].configure(text="308.7")
			aScale[12].configure(text="309")
			aScale[13].configure(text="309.7")
			aScale[14].configure(text="310")
			aScale[15].configure(text=">310.7")	

	else:
		logging.debug("Starting w/No GUI: "+now.strftime(settings.EPdateTimeFormat))
		addHistory("Starting w/No GUI")

	ErrorLabelTag = ""

	if (settings.serialOpen):															#27oct20 TJR
		cmdData = Queue()																#27oct20 TJR
		respData = Queue()																#27oct20 TJR
		serData = Thread(target=serialData, name="sData", args=(ser,cmdData,respData,))	#27oct20 TJR
		serData.setDaemon(True)															#27oct20 TJR
		serData.start()		
		time.sleep(settings.serialStartDelay)													#02nov20 TJR

		dataS = doComm("V",False)								#28oct20 TJR
		eol = dataS.find('\n') 									#28oct20 TJR
		logging.debug("Nano Version: "+dataS[:eol])				#28oct20 TJR
		dataS = doComm("C",False)								#28oct20 TJR
		posT = dataS.find('T,')									#27oct20 TJR
		eol = dataS.find('\n') 									#27oct20 TJR
		ScannerIRraw = float(dataS[posT+2:eol])					#27oct20 TJR

	time.sleep(0.1)															#10apr20 TJR		
	getIRpoint()
	if (ScannerIRraw != -999.0):											#08par20 TJR
		Msg = "Main Initialization - Starting Threads"	
		debug.LogAction(Msg, True)											#16mar17 TJR
		logging.debug(Msg)													#16mar17 TJR

		Qusers = Queue()	
		watcher = Thread(target=msgWatch, name="Messages", args=(Qusers,))
		watcher.setDaemon(True)
	
		IRdata = Queue()
		getIR = Thread(target=getIRdata, name="IRdata", args=(IRdata,))
		getIR.setDaemon(True)
		
		server = Thread(target=getConnections, name="Connects", args=(settings.TCPIPinAddr, settings.TCPIPinPort, Qusers,))
		server.setDaemon(True)

		watcher.start()
		time.sleep(0.1)
		getIR.start()
		time.sleep(0.1)
		sT0 = SecondTimer(1,SecondTick)
		time.sleep(settings.d1)

		WaitForDelay()
		ClearScanner()		
		time.sleep(settings.d2)
		server.start()
			
		if (settings.showGUI == True):		#09jul18 TJR
			root.after(1000,mainTick)
			root.mainloop()
		else:
			while (settings.showGUI == False):
				time.sleep(0.002)

		settings.serverRunning = False
		if (settings.serialOpen == True):
			ser.close()
		sT0.stop()
		ErrorLabelTag = "Aborted Scan"
		logging.debug("delay 1.1")
		time.sleep(1.1)

	else:
		settings.serverRunning == False
		if (settings.serialOpen == True):
			ser.close()

		ErrorLabelTag = "Can't Get Initial Surface Temp!!"					#21feb19 TJR
		if (settings.showGUI == True):										#07apr20 TJR
			Error_var.set(ErrorLabelTag)									#07apr20 TJR
		logging.debug(ErrorLabelTag)										#10apr20 TJR
		logging.debug("Initialization EXIT can't read Sensor")

	#exit()	#ErrorLabelTag   
